#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>

#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_err.h"
#include "nvs_flash.h"
#include "esp_netif.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

/*
 * Update these credentials before flashing.
 * Use a stable 2.4 GHz WPA2 network for best CSI results.
 */
#define WIFI_SSID "Connecting..."
#define WIFI_PASS "Error500"

#define STATS_PERIOD_MS 5000

static const char *TAG = "CSI_RECEIVER";

static volatile uint32_t g_csi_frames = 0;
static volatile uint32_t g_csi_bytes = 0;
static volatile uint32_t g_rx_packets = 0;
static volatile int32_t g_last_rssi = -127;
static bool g_csi_enabled = false;

static uint8_t g_ap_bssid[6] = {0};
static bool g_have_ap_bssid = false;

static void log_err(const char *op, esp_err_t err)
{
    if (err == ESP_OK)
    {
        ESP_LOGI(TAG, "%s: OK", op);
    }
    else
    {
        ESP_LOGE(TAG, "%s: %s", op, esp_err_to_name(err));
    }
}

static void wifi_csi_cb(void *ctx, wifi_csi_info_t *info)
{
    (void)ctx;

    if (info == NULL || info->len <= 0)
    {
        return;
    }

    g_csi_frames++;
    g_csi_bytes += (uint32_t)info->len;
    g_last_rssi = info->rx_ctrl.rssi;

    /*
     * Keep the legacy plain-integer format so the current Python pipeline and
     * saved datasets can consume new captures without parser changes.
     */
    printf("CSI_DATA:");

    for (int i = 0; i < info->len; i++)
    {
        printf(" %d", info->buf[i]);
    }
    printf("\n");
    fflush(stdout);
}

static void promiscuous_rx_cb(void *buf, wifi_promiscuous_pkt_type_t type)
{
    (void)buf;
    (void)type;
    g_rx_packets++;
}

static void update_ap_bssid(void)
{
    wifi_ap_record_t ap = {0};
    esp_err_t err = esp_wifi_sta_get_ap_info(&ap);
    if (err == ESP_OK)
    {
        memcpy(g_ap_bssid, ap.bssid, sizeof(g_ap_bssid));
        g_have_ap_bssid = true;
        ESP_LOGI(TAG,
                 "AP BSSID set: %02x:%02x:%02x:%02x:%02x:%02x RSSI=%d channel=%d",
                 g_ap_bssid[0], g_ap_bssid[1], g_ap_bssid[2],
                 g_ap_bssid[3], g_ap_bssid[4], g_ap_bssid[5],
                 ap.rssi,
                 ap.primary);
    }
    else
    {
        ESP_LOGW(TAG, "esp_wifi_sta_get_ap_info failed: %s", esp_err_to_name(err));
    }
}

static void ensure_csi_enabled(void)
{
    if (g_csi_enabled)
    {
        return;
    }

    /*
     * On some boards/firmware states, CSI enable can fail during early startup.
     * Retry after link-up events.
     */
    for (int attempt = 1; attempt <= 6; attempt++)
    {
        esp_err_t err = esp_wifi_set_csi(true);
        if (err == ESP_OK)
        {
            g_csi_enabled = true;
            ESP_LOGI(TAG, "esp_wifi_set_csi(true): OK (attempt %d)", attempt);
            return;
        }
        ESP_LOGW(TAG, "esp_wifi_set_csi(true) failed on attempt %d: %s", attempt, esp_err_to_name(err));
        vTaskDelay(pdMS_TO_TICKS(200));
    }

    ESP_LOGE(TAG, "CSI could not be enabled after retries");
}

static void wifi_event_handler(void *arg,
                               esp_event_base_t event_base,
                               int32_t event_id,
                               void *event_data)
{
    (void)arg;

    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START)
    {
        ESP_LOGI(TAG, "STA started, connecting...");
        esp_wifi_connect();
    }
    else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED)
    {
        wifi_event_sta_disconnected_t *disc = (wifi_event_sta_disconnected_t *)event_data;
        int reason = disc ? disc->reason : -1;
        g_csi_enabled = false;
        g_have_ap_bssid = false;
        ESP_LOGW(TAG, "WiFi disconnected, reason=%d, reconnecting...", reason);
        esp_wifi_connect();
    }
    else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_CONNECTED)
    {
        ESP_LOGI(TAG, "STA connected, enabling CSI...");
        update_ap_bssid();
        ensure_csi_enabled();
    }
    else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP)
    {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "WiFi connected. IP: " IPSTR, IP2STR(&event->ip_info.ip));
        update_ap_bssid();
        ensure_csi_enabled();
    }
}

static void wifi_init(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
                                                        ESP_EVENT_ANY_ID,
                                                        &wifi_event_handler,
                                                        NULL,
                                                        NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
                                                        IP_EVENT_STA_GOT_IP,
                                                        &wifi_event_handler,
                                                        NULL,
                                                        NULL));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = WIFI_SSID,
            .password = WIFI_PASS,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };

    log_err("esp_wifi_set_mode", esp_wifi_set_mode(WIFI_MODE_STA));
    log_err("esp_wifi_set_config", esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    log_err("esp_wifi_start", esp_wifi_start());

    log_err("esp_wifi_set_ps(WIFI_PS_NONE)", esp_wifi_set_ps(WIFI_PS_NONE));

    wifi_promiscuous_filter_t filt = {
        .filter_mask = WIFI_PROMIS_FILTER_MASK_DATA,
    };
    log_err("esp_wifi_set_promiscuous_filter", esp_wifi_set_promiscuous_filter(&filt));
    esp_wifi_set_promiscuous_rx_cb(promiscuous_rx_cb);
    log_err("esp_wifi_set_promiscuous(true)", esp_wifi_set_promiscuous(true));

    wifi_csi_config_t csi_cfg = {
        .lltf_en = true,
        .htltf_en = true,
        .stbc_htltf2_en = true,
        .ltf_merge_en = true,
        .channel_filter_en = false,
        .manu_scale = false,
        .shift = false,
    };

    log_err("esp_wifi_set_csi_config", esp_wifi_set_csi_config(&csi_cfg));
    log_err("esp_wifi_set_csi_rx_cb", esp_wifi_set_csi_rx_cb(wifi_csi_cb, NULL));
    ESP_LOGI(TAG, "CSI callback configured. CSI enable will be retried on connect events.");
}

void app_main(void)
{
    ESP_LOGI(TAG, "====================================");
    ESP_LOGI(TAG, "WiFi CSI Receiver (ESP-IDF 5.x)");
    ESP_LOGI(TAG, "====================================");

    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND)
    {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    wifi_init();

    uint32_t prev_csi = 0;
    uint32_t prev_rx = 0;
    while (1)
    {
        vTaskDelay(pdMS_TO_TICKS(STATS_PERIOD_MS));

        if (!g_csi_enabled)
        {
            ESP_LOGW(TAG, "CSI still disabled, retrying enable...");
            ensure_csi_enabled();
        }

        uint32_t csi_now = g_csi_frames;
        uint32_t rx_now = g_rx_packets;
        uint32_t csi_delta = csi_now - prev_csi;
        uint32_t rx_delta = rx_now - prev_rx;
        prev_csi = csi_now;
        prev_rx = rx_now;

        ESP_LOGI(TAG,
                 "CSI stats: total=%lu delta=%lu bytes=%lu | RX packets total=%lu delta=%lu | last_rssi=%ld",
                 (unsigned long)csi_now,
                 (unsigned long)csi_delta,
                 (unsigned long)g_csi_bytes,
                 (unsigned long)rx_now,
                 (unsigned long)rx_delta,
                 (long)g_last_rssi);
    }
}