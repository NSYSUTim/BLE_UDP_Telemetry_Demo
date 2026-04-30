# Outdoor Telemetry Prototype: Hybrid BLE/UDP Testbench

這是一個基於 Raspberry Pi 實作的戶外穿戴式裝置通訊原型與自動化測試平台。本專案模擬了戶外 GPS 記錄器（Wearable Device）與手機端（Companion App）的資料同步流程，涵蓋裝置發現、狀態機模擬、即時資料傳輸與自動化測試產出。

## 💡 專案亮點與工程決策 (Engineering Trade-offs)

在原型開發階段，由於 Raspberry Pi 上的 Linux BlueZ 藍牙守護進程與 Python D-Bus 在處理高頻率 BLE GATT Notification 時，容易產生 IPC 型別轉換與阻塞問題。為了在有限的硬體資源下驗證完整的測試平台邏輯，本專案採用 **混合式通訊架構 (Hybrid Architecture)**：
1. **BLE Advertising & Discovery:** 保留 BLE 機制處理裝置廣播與握手，精準模擬真實穿戴裝置被手機端掃描與發現的流程。
2. **UDP Telemetry Transport:** 將高頻率的即時 GPS 活動資料（Telemetry）改由 UDP 進行可靠且低延遲的傳輸，確保自動化測試管線的穩定性。

## 🏗️ 系統架構

本系統由兩台 Raspberry Pi 組成，分別扮演 Peripheral 與 Central 的角色：

* **Device 1: 戶外裝置模擬器 (BLE Peripheral + UDP Sender)**
  * 使用 `bless` 建立 GATT Service 並進行 BLE 廣播。
  * 內部實作活動狀態機，模擬產生包含 `序號`、`速度`、`距離` 與 `GPS 狀態 (Tracking/Lost)` 的即時活動資料。
  * 透過 UDP Socket 將打包好的 JSON 資料推播至測試端。

* **Device 2: 測試驗證平台 (BLE Central + UDP Receiver)**
  * 使用 `bleak` 進行環境掃描，驗證裝置是否成功上線並解析 GATT 特徵值。
  * 啟動 UDP 接收器收集 30 秒的 Telemetry 串流資料。
  * 具備自動化驗證機制，結束後自動產出 CSV 日誌檔 (`telemetry_log.csv`) 與自動化測試報告 (`test_report.txt`)。

## ⚙️ 環境與安裝需求

* 兩台 Raspberry Pi (測試環境為 Debian Trixie)
* Python 3.13+ 
* 系統套件：`bluez`, `bluetooth`, `pi-bluetooth`, `rfkill`

### 建立虛擬環境與安裝依賴

在兩台裝置上皆需建立虛擬環境並安裝對應的 Python 函式庫：
```bash
# 建立並啟動虛擬環境
python3 -m venv .venv
source .venv/bin/activate

# Pi 1 安裝 bless
pip install bless

# Pi 2 安裝 bleak
pip install bleak
