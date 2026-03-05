#include <stdio.h>
#include <string.h>
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "esp_netif.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

// ============================================
// CONFIGURATION - Change these for your WiFi
// ============================================
#define WIFI_SSID "Connecting..."
#define WIFI_PASS "Error501"

// CSI data rate control (adjust for stability)
#define CSI_SEND_RATE_MS 100  // Send CSI every 100ms (10 Hz)

static const char *TAG = "CSI_PRESENCE_DETECTOR";

/* CSI callback function - called when CSI data is available */
static void wifi_csi_cb(void *ctx, wifi_csi_info_t *info)
{
    if (!info || info->len == 0)
    {
        return;  // Skip invalid data
    }
    
    // Output CSI data in parseable format
    printf("CSI_DATA:");
    for (int i = 0; i < info->len; i++)
    {
        printf(" %d", info->buf[i]);
    }
    printf("\n");
    
    // Optional: Rate limiting via task delay (handled in main loop)
    fflush(stdout);  // Ensure data is sent immediately
}

/* Promiscuous RX callback (IMPORTANT FIX) */
static void promiscuous_rx_cb(void *buf, wifi_promiscuous_pkt_type_t type)
{
    // No processing needed, just enabling full packet capture
}

/* WiFi event handler - connection status management */
static void wifi_event_handler(void* arg,
                               esp_event_base_t event_base,
                               int32_t event_id,
                               void* event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START)
    {
        ESP_LOGI(TAG, "Station started, connecting to WiFi...");
        esp_wifi_connect();
    }
    else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED)
    {
        ESP_LOGW(TAG, "Disconnected from WiFi, reconnecting...");
        esp_wifi_connect();
    }
    else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP)
    {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(TAG, "✓ WiFi Connected! IP: " IPSTR, IP2STR(&event->ip_info.ip));
        ESP_LOGI(TAG, "✓ CSI system active - presence detection ready");
    }
}

/* WiFi initialization with CSI enabled */
void wifi_init()
{
    // Initialize TCP/IP network interface
    esp_netif_init();
    esp_event_loop_create_default();
    esp_netif_create_default_wifi_sta();

    // Initialize WiFi with default configuration
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    esp_wifi_init(&cfg);

    // Register event handlers for WiFi connection status
    esp_event_handler_instance_register(WIFI_EVENT,
                                        ESP_EVENT_ANY_ID,
                                        &wifi_event_handler,
                                        NULL,
                                        NULL);

    esp_event_handler_instance_register(IP_EVENT,
                                        IP_EVENT_STA_GOT_IP,
                                        &wifi_event_handler,
                                        NULL,
                                        NULL);

    // Configure WiFi credentials
    wifi_config_t wifi_config = {
        .sta = {
            .ssid = WIFI_SSID,
            .password = WIFI_PASS,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };

    // Set WiFi mode and configuration
    esp_wifi_set_mode(WIFI_MODE_STA);
    esp_wifi_set_config(WIFI_IF_STA, &wifi_config);
    esp_wifi_start();

    // ============================================
    // CRITICAL CSI CONFIGURATION
    // ============================================
    
    // Disable power saving for continuous CSI data
    esp_wifi_set_ps(WIFI_PS_NONE);
    ESP_LOGI(TAG, "✓ Power saving disabled for continuous CSI");

    // Enable promiscuous mode to capture all packets
    esp_wifi_set_promiscuous(true);
    esp_wifi_set_promiscuous_rx_cb(promiscuous_rx_cb);
    ESP_LOGI(TAG, "✓ Promiscuous mode enabled");

    /* Configure CSI parameters for optimal presence detection */
    wifi_csi_config_t csi_config = {
        .lltf_en = true,           // Enable Legacy Long Training Field
        .htltf_en = true,          // Enable HT Long Training Field  
        .stbc_htltf2_en = true,    // Enable STBC HT-LTF2 field
        .ltf_merge_en = true,      // Merge LTF data
        .channel_filter_en = false, // Disable channel filter
        .manu_scale = false,       // Automatic scaling
        .shift = false             // No bit shifting
    };

    esp_wifi_set_csi_config(&csi_config);
    esp_wifi_set_csi_rx_cb(&wifi_csi_cb, NULL);
    esp_wifi_set_csi(true);

    ESP_LOGI(TAG, "✓ CSI configured and enabled");
    ESP_LOGI(TAG, "================================");
    ESP_LOGI(TAG, "CSI Presence Detection Ready");
    ESP_LOGI(TAG, "================================");
}

/* Main entry point */
void app_main()
{
    ESP_LOGI(TAG, "");
    ESP_LOGI(TAG, "====================================");
    ESP_LOGI(TAG, "  WiFi CSI Presence Detector");
    ESP_LOGI(TAG, "  ESP32 Firmware v1.0");
    ESP_LOGI(TAG, "====================================");
    ESP_LOGI(TAG, "");
    
    // Initialize NVS (required for WiFi)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND)
    {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    
    // Initialize WiFi with CSI
    wifi_init();
    
    ESP_LOGI(TAG, "System running. CSI data will be output continuously.");
    ESP_LOGI(TAG, "Connect serial to Python detector for presence detection.");
    
    // Main loop - keep the system running
    while (1)
    {
        // Add small delay to control CSI output rate
        vTaskDelay(pdMS_TO_TICKS(CSI_SEND_RATE_MS));
    }
}