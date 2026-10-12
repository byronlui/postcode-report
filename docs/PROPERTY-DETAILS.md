# 成交物業補充資料

成交表格顯示面積 m²、睡房、浴室、資料日期及來源。Land Registry PPD 不包含這些欄位；無資料顯示「未提供」，不推斷或從房屋類型估算。EPC 可居住房間數不等於睡房數。

地址連結使用 Google Maps 官方 search URL（地址＋完整 postcode＋UK），不是已核實的定位／place ID。

如有合法取得且核實的物業資料，複製 `datasets/property-details-template.csv` 至 `data/property-details.csv`，用 UTF-8 CSV 填寫。地址請與成交表格文字一致（包括 flat／unit），postcode 必須相同。只忽略大小寫、空白和標點，不做模糊配對。source 填寫資料來源或原始網址，observed_date 填 YYYY-MM-DD。不可填寫推測數字。面積指室內樓面面積，不是地皮或花園面積；使用前核實來源口徑。

同一地址多筆補充資料會視為有歧義而不顯示數值；請先整理成一筆核實紀錄。數值必須非負且有限；面積須大於零，睡房／浴室須整數。資料日期及來源必填。檔案在每次成交查詢重新讀取，重新搜尋即可生效。

此補充檔是手動資料，沒有自動更新承諾，並非成交當日規格。EPC 自動配對及其設定要求見下節。

官方成交欄位：https://www.gov.uk/guidance/about-the-price-paid-data

## Housemetric 類似指標與 EPC 接駁

Housemetric FAQ (https://housemetric.co.uk/faq) 說明面積主要來自 EPC，成交來自 HMLR。本站新增 EPC 完整地址配對（不輸出 EPC 原始地址）、最新能源級別、歷次 EPC、可居住房間、平方米／平方呎及成交 £/m²。

在網站輸入本次 EPC token 後，自動查詢官方 domestic/search 及 certificate API；每次最多 40 份證書，搜尋超過一頁會提示。未設 token 可使用現有 `scripts/import_data.py epc` 匯入官方 CSV，須重新匯入才能保存新增面積、房間及地址配對摘要。完整地址不符、不同 UPRN 或同日衝突不強行配對。最新 EPC 面積不等於歷史成交當日面積；EPC 房間數不是睡房／浴室。

沒有 token／匯入資料時欄位留空並顯示設定提示；沒有抓取 Housemetric 物業資料。官方 API schema：https://github.com/communitiesuk/epb-data-warehouse/blob/main/api/api.yml 。證書 JSON 依 schema 版本不同，優先使用根層 total_floor_area / habitable_room_count / dwelling_type，主樓年代只取 building_part_number=1；按 schema_type 查官方代碼表，絕不使用證書日期代替建築日期。

## 2026-09-23 列表及物業詳情

預設每個地址只顯示查詢範圍內最近成交，提供日期、價格、面積及 £/m² 排序，缺失資料置後。地址可開啟物業詳情；另有 Google Maps 連結。詳情顯示成交歷史、兩次成交總升幅（非年化）、按最新面積計算的歷史單價、睡房／浴室及 EPC 歷次紀錄。無授權廣告來源時不展示照片及平面圖，亦不產生估值。

實際核對 RG5 3AB：129 筆成交；66 HANWOOD CLOSE 的 2025-03-19 £400,000、2017-03-10 £300,000、2011-01-31 £195,000 在 API 與瀏覽器詳情一致。


## 2026-09-26 EPC linkage correction

Sale address matching includes locality and town supplied by Land Registry, while retaining flat/unit numbers. Latest certificates for distinct properties take priority over historical certificates within the 40-detail request budget. The table shows EPC habitable rooms separately from independently sourced bedrooms, and reports unmatched addresses or missing authorisation explicitly. EPC translated value objects are rendered as plain text.

Browser verification for RG5 3AB displayed 66 Hanwood Close: 77 m², end-terrace house, 5 habitable rooms. Bedrooms remain unavailable without an independent source; habitable rooms must not be converted into bedrooms. Tokens remain confined to the existing temporary session mechanism.

## 2026-10-10 address and full certificate facts

Live EPC responses now include the address and postcode, a map link, and expandable allowlisted energy, CO2, inspection, heating, lighting, window, floor, roof and wall facts. Nested official schema components remain separate; codes without a verified mapping are labelled as official codes. Missing fields are not inferred. The public-data CSV import continues to omit address text; live authorised responses are not persisted. Official sample checked: communitiesuk/epb-data-warehouse/spec/fixtures/json_samples/RdSAP-Schema-20.0.0/epc.json.

School details use 48% of the desktop explorer width (60% in wide reading mode), with no fixed-height sidebar clipping. At 1920px the normal sidebar measured approximately 748px. 71 tests pass. Real account certificate retrieval requires re-entering the runtime token after restart.
