#include <stdio.h>
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"

static const char *TAG = "CSI";

static void wifi_csi_cb(void *ctx, wifi_csi_info_t *info)
{
    printf("CSI_DATA: ");
    for (int i = 0; i < info->len; i++)
    {
        printf("%d ", info->buf[i]);
    }
    printf("\n");
}

void wifi_init()
{
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    esp_wifi_init(&cfg);

    esp_wifi_set_mode(WIFI_MODE_STA);
    esp_wifi_start();

    wifi_csi_config_t config = {
        .lltf_en = true,
        .htltf_en = true,
        .stbc_htltf2_en = true,
        .ltf_merge_en = true,
        .channel_filter_en = false,
        .manu_scale = false,
        .shift = false
    };

    esp_wifi_set_csi_config(&config);
    esp_wifi_set_csi_rx_cb(&wifi_csi_cb, NULL);
    esp_wifi_set_csi(true);
}

void app_main()
{
    nvs_flash_init();
    esp_event_loop_create_default();
    wifi_init();
}

