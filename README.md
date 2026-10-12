# postcode-report
Initial assessment / Preliminary inspection using free and open data

# 免費仔 free rider：自動安裝及啟動

如需使用，請自行申請EPC的API Key，需要使用者自行使用GOV.UK ONE賬號申請。
https://get-energy-performance-data.communities.gov.uk

更新：2026-10-11。Python 版本；原始碼包括 Python、HTML、CSS、JavaScript、資料匯入工具及測試。


## 1. 選擇下載包

- `Open-Neighbourhood-with-data.zip`：建議使用。包括全部原始碼及已下載的公開資料快照，首次使用較快。
- `Open-Neighbourhood-source.zip`：原始碼小包；首次查詢部分功能需要下載公開資料。

只需選一個。解壓後得到 `postcode-report` 資料夾。請把整個資料夾放在你自己的電腦，例如 Documents；不要只下載安裝腳本。不要在 ZIP 裏直接執行。

## 2. Mac：首次安裝

1. 確保有互聯網，預留至少 5 GB 空間。
2. 安裝 Python 3.11 或以上：https://www.python.org/downloads/macos/ 。如果電腦已有合適版本可跳過。安裝程式需要你按系統畫面完成；本腳本不會自行取得管理員權限。
3. 在解壓後的資料夾雙擊 **Install-and-Start.command**。
4. 等待 Terminal 安裝套件。腳本會建立 `.venv`、安裝 requirements、首次建立 `.env`，並檢查程式能否載入；既有 `.env` 和 data 不會被覆寫。
5. 安裝完成後自動啟動網站及打開瀏覽器：http://127.0.0.1:8765/ 。如瀏覽器未自動開啟，手動打開此網址。
6. 輸入郵編，例如 `RG10 9RZ`。首次資料下載可能需要數分鐘；請查看網站資料來源狀態。
7. EPC 功能需要在網站輸入你自己的 token。下載包沒有 token；它只在伺服器記憶體暫存，重啟後需要重新輸入。

沒有 Python 時，腳本會顯示提示並在 Mac 打開官方下載頁。裝好後再次雙擊即可。

如果 macOS 不允許雙擊執行，開啟 Terminal，輸入 `cd `（後面一個空格），把解壓後的 `postcode-report` 資料夾拖入，再按 Enter。接着執行：

```sh
sh install.sh
```

## 3. 每次啟動與停止

- 下次只需雙擊 **Start.command**；不用重新安裝。亦可在資料夾內執行 `sh launch.sh`。
- 保持 Terminal 視窗開啟。停止時在該視窗按 **Control+C**。
- 同一部電腦只啟動一次。如果 8765 已被使用，可打開既有網站，或使用 `PORT=8766 sh launch.sh`，網址改為 http://127.0.0.1:8766/ 。
- 安裝但暫不啟動：`sh install.sh --install-only`。
- 更換電腦時重新解壓及安裝，不要複製 `.venv`。

## 4. Linux / Windows

Linux 需要 Python 3.11+ 和 venv。Ubuntu 可先執行：

```sh
sudo apt update
sudo apt install python3 python3-venv python3-pip unzip
```

解壓並進入 `postcode-report` 後執行 `sh install.sh`。請先用 `python3 --version` 確認版本。

Windows 請使用 **WSL2 Ubuntu**，不支援直接在 Windows 原生 Python 執行（程式使用 Unix 檔案鎖）。先依 Microsoft 指引安裝：https://learn.microsoft.com/windows/wsl/install 。在 Ubuntu 裏按照上面的 Linux 步驟操作；建議把專案解壓至 WSL 的 home 資料夾。可用 Windows 瀏覽器開啟 localhost 網址。macOS `.command` 檔只供 Mac 使用。

## 5. 常見問題

- 安裝失敗：保留錯誤文字，檢查網絡及 Python 版本，再執行 `sh install.sh`。安裝需要從 Python 套件庫下載檔案。
- 出現 SSL / certificate 錯誤：使用 python.org Mac 安裝版本時，可在 Applications/Python 版本資料夾執行 `Install Certificates.command`，再重試。
- 網頁無法開啟：查看 Terminal 是否仍運行，網址是 `http`，不是 `https`。
- 外部資料暫時失敗：網站會顯示來源狀態；稍後重試。資料快照並不代表所有來源都即時更新。
- 地質為區域概要、Radon 為網格資料；不是個別住宅測量。EPC 可居住房間數不等於睡房數；未知資料會標示未提供。
- 備份：停止伺服器後複製整個資料夾；`.env` 如包含你自行設定的其他服務金鑰，請自行保管。

進階設定及資料匯入請見 README.md 和 docs/INSTALL-繁體中文.md。本快速指南的自動安裝步驟優先於舊版手動安裝步驟。



##############################################################################

# 免費仔 free rider — UK postcode property / area report

可運行的 **Python FastAPI + SQLite + 原生 HTML/CSS/JavaScript** starter。繁體中文 dashboard，輸入 UK postcode 即可查詢；預設 `RG10 9RZ`。來源分開顯示資料年份、查詢範圍、快取時間、授權及限制。

這不是 CrystalRoof clone：只參考其公開可見的 **分類名稱**，程式、介面、分析和資料均獨立實作；沒有登入、繞過付費牆或下載其商業數據。詳細對照見 [docs/OPTIONS.md](docs/OPTIONS.md)。

目前以 **Python 版本**為主；舊 PHP 匯出不再更新。學校地圖已加入右鍵選址、直線距離、左側資料選單、官方學生／收生／師資資料及 KS2 地區比較。操作、資料匯入及尚未接駁項目見 [學校功能說明](docs/SCHOOLS.md)。

每次開啟／搜尋會自動檢查已接駁來源版本，有變更便下載及匯入，成功後自動重載報告。水浸頁現以 **歷史水浸範圍** 為主，可選過去一年至全部年份。詳細機制、適用範圍及不能保證最新的項目見 [更新與水浸紀錄說明](docs/FRESHNESS.md)。

## 快速開始

需要 Python 3.11+；本次在 macOS / Python 3.14 實測。

```sh
cd postcode-report
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
./start.sh
```

打開 **http://127.0.0.1:8765**。API 說明在 **http://127.0.0.1:8765/docs**。`start.sh` 只綁定本機，沒有公開部署或註冊外部網站。

交付工作目錄已有全國 NaPTAN、England GIAS、GB OS Open Greenspace 本地索引及 RG10 9RZ 真實 API 快取。新安裝沒有索引時，可執行：

```sh
.venv/bin/python scripts/bootstrap_data.py
```

此步下載約 170 MB 壓縮／CSV 原始資料（解壓及 SQLite 額外需要數百 MB），需外網；**沒有**假資料。可用 `--only schools`、`--only transport`、`--only greenspace` 個別更新。GIAS 使用 DfE 每日公開 CSV（支援版本日期及條件式下載）；若自動下載失敗，在官方 Downloads 頁下載 **Establishment fields CSV**，再用下面的 importer。`--reuse` 只供已知版本的本地下載檔重建；不會驗證檔案仍為最新版。

## 包含甚麼

| 分類 | 可運作內容 | 重要界線 |
|---|---|---|
| Overview | 郵區定位、council、ward、LSOA 2021、OSM 地圖、概覽 | 郵區中心不是物業地塊 |
| Affluence | Census 最高學歷／住屋業權；官方收入或 IMD CSV 匯入 | 未建立商業富裕評分；學歷不是收入 |
| Crime | 最新可用月份、自訂半徑／地圖框選、事件位置及分類數量 | 包括 ASB；匿名位置；不稱為犯罪率 |
| Demographics | 最新年度人口／年齡估算、Census 2021 種族及 tenure | England/Wales LSOA 2021；每項分開標示統計年份 |
| Noise | Defra round 4 道路及鐵路 Lden / Lnight 郵區點查詢；GeoJSON 後備 | 2021 模型、10 m 格網；不是現場讀數 |
| Transport | NaPTAN 5 km 站點／入口；直線距離；目的地 postcode；TfL journey API | TfL 非全英 journey engine；無法保證任何英國路線均有時間／票價 |
| Amenities | FSA 2 miles 食品商戶及衛生資料；NHS 官方入口 | FSA 並非所有商店／醫療服務清單 |
| Schools | GIAS 自訂距離、地圖篩選、DfE 成績、Ofsted、最多四校比較 | GIAS 也有 nursery / colleges / special settings；用類型篩選；不判定 catchment |
| Environment | EA 歷史水浸範圍（時間／距離篩選）、規劃 flood-risk-zone、OS 綠地入口、UK-AIR 監測站 adapter | 沒有警報不代表低風險；postcode 點相交不是物業水浸評估 |
| Reviews | 按 postcode 儲存私人睇樓筆記 | 瀏覽器本地存放，無官方／商業居民評論來源，不發布 |
| Sold prices | Land Registry postcode 成交、物業類型、年度中位數 | England/Wales；最多最近 500 筆；無 bedrooms，不能假裝篩選 4-bed |
| EPC | **新** MHCLG bearer-token API；歷次證書、能源級別、面積、類型及主樓年代 | 需 GOV.UK One Login；沒有 key 時明確提示；不發布地址欄位 |
| Broadband/mobile | 免 key 官方下載：postcode 寬頻覆蓋 + 地方政府 mobile 統計 | 2026-01 快照；手機不是 postcode／個別網絡商預測；即時 API 另需 key |
| Council Tax | 按 council + parish 匯入年度各 band 收費；VOA/SAA 入口 | postcode 無法決定房屋 band；NI 用 rates |
| Planning | 中心點限制圖層、附近約 2 × 2 km 申請查詢、council 入口 | England API 不完整；零筆不能解讀為沒有申請 |

距離設定：學校、交通站點、食品／餐廳、綠地各自可輸入搜尋半徑，支援公里（0.1–50）或英里（0.1–30）。按「更新範圍」重新查詢；設定儲存在本瀏覽器，JSON 匯出亦沿用已套用半徑。名單上限仍適用。Reading School / The Piggott School 為固定關注學校，另列且不受半徑限制。距離均為郵區中心直線距離。

其他功能：資料表篩選及分頁、成交趨勢圖、JSON 報告下載、列印目前分類、響應式版面、逐來源重試。JSON 包含所有 server-side sections，不包括私人筆記。列印只列印當前畫面，不是完整 PDF 匯出。

## 網絡免 key；EPC 一次性登入

網絡覆蓋已改用 Ofcom OGL 公開下載，工作目錄已匯入 1,741,096 個 postcode。新安裝執行：

```sh
.venv/bin/python scripts/import_ofcom.py --download
```

約 34 MB 下載，載入 2026-01 固定寬頻及手機資料。寬頻用修正後 postcode r2；mobile 是地方政府全區統計，不代表某個 postcode 的各網絡商訊號。沒有 key 亦可運作；下一次官方 release 要更新 importer 的版本與 schema，不會把舊資料稱為即時。

EPC 官方 API 要求授權。登入 [EPC 官方服務](https://get-energy-performance-data.communities.gov.uk/guidance/energy-certificate-data-apis) 後取得 bearer token，直接在網站啟動時的「EPC 本次使用授權」輸入框填入；亦可按頁頂「EPC 授權」。不再使用 `.env` 儲存 EPC token，舊 `configure_epc.py` 只顯示新操作說明。

Token 僅暫存在單一伺服器程序的記憶體，授權一小時；關閉伺服器或按「清除授權」即失效。瀏覽器只有 HttpOnly / SameSite=Strict 的隨機 session ID cookie，不保存 token；不寫入 SQLite、localStorage、設定、日誌或下載包。EPC 授權 API 回應也不使用磁碟快取。每頁啟動均提示授權，可選「稍後」。目前用 localhost 的單程序模式；對外部署須使用 HTTPS，並勿啟用記錄 request body / Authorization 的代理日誌。多 worker 不共享此記憶體 session。

證書按日期排序，每次最多 40 份詳細資料；不足、分頁和失敗清楚標示。其餘證書可按各卡片的「重新取得此證書詳情」逐份讀取。官方 `dwelling_type`、`total_floor_area`、主樓 `construction_age_band` 配合 schema 對應代碼表解讀；缺失不猜測。建築年代不是準確落成日，證書 completion/registration date 不會當作建築日期。也可自行下載官方 domestic CSV 匯入：

```sh
.venv/bin/python scripts/import_data.py epc /path/to/certificates.csv --source https://get-energy-performance-data.communities.gov.uk/ --vintage YYYY-MM-DD --license 'EPC non-address fields OGL; postcode lookup restrictions apply'
```

## 可選 API key / 註冊

[.env.example](.env.example) 是其他可選服務的伺服器設定；EPC 另用下述工作階段輸入：

- EPC：使用网站的單次授權輸入框，沒有 EPC 環境變數。
- `OFCOM_API_KEY`：可選即時 Ofcom broadband subscription；公開快照不需要。Adapter endpoint 為 `https://api-proxy.ofcom.org.uk/broadband/coverage/{postcode}`。沒有使用者 key，故本次沒有驗證授權後的真實回應。
- `OFCOM_MOBILE_URL`、`OFCOM_MOBILE_KEY`：從[新 mobile portal](https://apim-cnapi-shared-prod.developer.azure-api.net/)取得獲授權 endpoint template，必須含 `{postcode}`。只接受官方 gateway HTTPS hostname。這是可配置 raw JSON adapter，**不是**已驗證的所有 mobile 方案統一 schema。舊 mobile API 停用日期為 2026-11-30。
- `TFL_APP_KEY`：可選，用於 TfL 配額；其他全英旅程請使用 National Rail / Traveline 官方 planner。沒有虛構由直線距離換算的通勤時間。
- `ENABLE_OSM=false`：預設只用官方資料作配套查詢。若啟用，額外 OSM Overpass 社群資料按 ODbL 歸屬；本次 Overpass 回傳 406，因此主流程已改用官方 OS 綠地資料，不依賴此服務。

EPC 及 Ofcom 授權是可選功能；缺少時不阻止其他分類。EPC 輸入立即生效，其他環境變數變更後重啟。完整來源／授權矩陣見 [docs/SOURCES.md](docs/SOURCES.md)。

## 本地資料匯入

```sh
# 官方 NaPTAN 原始 CSV
.venv/bin/python scripts/import_data.py transport data/naptan.csv --source https://naptan.api.dft.gov.uk/v1/access-nodes --vintage 2026-09-19 --license 'OGL v3.0'

# 官方 GIAS establishment fields CSV，或只包含一個 CSV 的 ZIP
.venv/bin/python scripts/import_data.py schools data/gias.zip --source https://www.get-information-schools.service.gov.uk/Downloads --vintage 2026-09-19 --license 'OGL v3.0'

# HMLR 16 欄、無標題原始 CSV；支援 A / C / D 增改刪及 transaction ID 去重
.venv/bin/python scripts/import_data.py prices data/pp-monthly.csv --source https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads --vintage 2026-08 --license 'OGL v3.0'

# OS 官方 GeoPackage (EPSG:27700)，只讀入口點並轉換座標
.venv/bin/python scripts/import_greenspace.py data/greenspace.gpkg --vintage 2026-04

# 已查證 Charvil 2026/27 官方年費，並非 postcode 物業 band
.venv/bin/python scripts/import_data.py tax datasets/charvil-tax-2026.csv --source 'https://www.wokingham.gov.uk/council-tax/guidance/charges-and-increases' --vintage 2026/27 --license 'Wokingham published charges; attribution retained'
```

所有 importer 以 transaction 執行，格式失敗不破壞舊索引。PPD 是增量 upsert / delete；其他 kind 是**替換整個已匯入 kind**，多個 councils / 地區請先合併檔案再匯入。首次 PPD 應匯入所需完整年度／完整快照，再按月更新，否則只有更新檔子集。API 當機時才使用本地 PPD，不會偷偷混合两個樣本。

其他 normalized CSV / GeoJSON schema 見 [docs/IMPORTS.md](docs/IMPORTS.md)。提供 importer 不等於已下載該項資料；界面會誠實顯示 setup / coverage 狀態。

## Database / cache 策略

SQLite `data/report.sqlite3`，WAL 模式：

- `cache`：URL + query + credential hash 的 SHA-256 key；JSON/text response、UTC fetched timestamp。token 不作明文 key。EPC 完全繞過此快取。其他授權服務仍需保護本地資料庫，不公開下載 DB。
- `points`：交通、學校、綠地入口、air；`kind, lat, lon` 索引，bounding box 預選再 Haversine 精算。
- `records`：PPD、EPC、mobile 地區統計、tax、社經表；postcode / area 索引。
- `ofcom_fixed`：postcode 主鍵及數值覆蓋比例；整份官方快照以 transaction 替換，匯入失敗保留舊版。
- `polygons`：匯入 WGS84 噪音等值區 bounding box + Shapely covers。
- `imports`：source URL、資料版本、匯入時間、匯入筆數、license。PPD 筆數指本次處理行數，不代表完整歷史總數。

TTL：postcode / census / noise 30 天；prices / FSA / Ofcom 7 天；crime / planning 1 天；EPC 不用磁碟快取；EA alerts 15 分鐘；journeys 5 分鐘。政府資料有更新節奏，TTL 不等於資料產生日期。

每程序最多 5 個並行上游請求；同 key 請求合併；timeout 預設 20 秒；最多一次暫時性錯誤重試；短 `Retry-After` 會遵從，長限流不重試。單分類 deadline 48 秒。可接受歷史來源遇故障時可顯示有限期 stale cache，**附原擷取時間及 stale 標記**；警報／journey／授權 EPC/Ofcom 不回退 stale。401 / 403 不用舊資料掩蓋。API 錯誤不會變成零事件或「安全」。

本地簡單限流每 IP 每分鐘 90 API requests。此 starter 非 multi-tenant 服務；要公開部署，請另加身份驗證、共享限流、磁碟維護、job queue、資料庫遷移及 secrets 管理。大量／全國 spatial workloads 建議 PostgreSQL + PostGIS 和排程 ingest；不要逐屋查公共 API。

## 測試與實測

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/smoke.py
```

Tests 使用 isolated temporary SQLite 和 mocked upstream，涵蓋 validation / injection、距離、半徑、快取合併、stale/auth、country coverage、EPC 去重和地址最小化、PPD 更正／刪除／rollback、routes/security。`smoke.py` 需外網，將**實際**成功、需要 key、失敗逐項寫到 [docs/rg109rz-live-report.json](docs/rg109rz-live-report.json)；不得把未執行的授權服務算作成功。

實測結果及瀏覽器 QA 見 [docs/VALIDATION.md](docs/VALIDATION.md)。`requirements.lock.txt` 記錄本次版本，可用 `pip install -r requirements.lock.txt` 重現；`requirements.txt` 是兼容範圍。

## API

- `GET /api/location/{postcode}` — 定位；錯誤格式 422，不存在 404，上游失敗 503。
- `GET /api/catalog` — 15 個界面 options + 來源清單。
- `GET /api/report/{postcode}/{section}` — 單分類；學校／交通／食品／綠地可用 `?radius_km=2`（0.1–50）；可用 section 見 `app/providers.py`。
- `GET /api/report/{postcode}` — 一次取得所有獨立 sections。
- `GET /api/journey?origin=RG109RZ&destination=EC2M7PY` — 目的地定位、直線距離、TfL 可提供的路線。
- `GET /health` — 本地服務狀態，並非外部 API 的健康保證。

所有原始來源視作不可信輸入；HTML escaping、safe links、CSP、不把上游內容當指令。Leaflet 1.9.4 地圖程式已連同授權放入本機；沒有前端 API key。

完整 JSON endpoint 接受 `schools_radius_km`、`transport_radius_km`、`amenities_radius_km`、`green_radius_km`，回應 `search_radii_km` 記錄所用範圍。

學校 API、來源授權、匯入及罪案地圖限制：見 [SCHOOLS.md](docs/SCHOOLS.md)。

人口資料年份、種族分類及更新方法：[DEMOGRAPHICS.md](docs/DEMOGRAPHICS.md)。

完整個人電腦安裝說明：[繁體中文說明書](docs/INSTALL-繁體中文.md)（另附可用瀏覽器開啟／列印的 HTML 版本）。

## 2026-09-23 更新

- 學校成績改為可換行的指標／結果兩欄；大型比較表在自己範圍內水平捲動。
- 罪案以警方可用月份選單選擇年月，保持所選半徑／矩形；JSON 匯出亦使用該月份。月份代表警方統計月份，不是確切案發日。
- 年度人口顯示最新六個已發布年度、逐年增減與百分比。種族比較使用 2011 QS201EW 與 2021 TS021 的五大類；僅當 LSOA 代碼一致才展示，並列可比性限制。沒有近年逐年種族估算。
- 通勤輸入 postcode 後以 OSRM / OpenStreetMap 顯示行車路線與非即時交通估算，另提供 Google Maps 公共交通／行車／步行／單車連結。TfL 可用時另列班次。OSRM 公開示範服務不保證可用性，正式大量使用應自行部署；Google Maps URL 不需要 API key。
- 測試與實際資料證據見 `docs/QA-2026-09-23.md`。
