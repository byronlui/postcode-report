# 公開 navigation 核對及實作對照

核對日期：2026-09-19。

用戶提供的 [RG10 9RZ transport 頁](https://crystalroof.co.uk/report/postcode/RG109RZ/transport) 可在正常瀏覽器開啟；一般網頁讀取工具當時失敗，故改以瀏覽器查看公開呈現的 UI。

可見主報告 navigation，依原先次序：

1. Overview
2. Affluence
3. Crime
4. Demographics
5. Noise
6. Transport
7. Amenities
8. Schools
9. Environment
10. Reviews

以上全部在本 app 有對應 tab。另加用戶指定的 Sold prices、EPC / Energy、Broadband / Mobile、Council Tax、Planning，共 15 tabs。界面名稱是功能對照，不代表商業網站所有隱藏 sub-options 或資料欄位已達同等覆蓋。

頁面上其他可見全站 actions 包括估值推廣、For Businesses、Review your area、Find Mortgage Broker、Pricing、Login；這些不是 postcode report 的資料分類。此 starter 不提供收費、登入、經紀導流、商業估值或商業 API 服務。Reviews 以不公開的私人筆記實作，不借用他人評論。

頁面部分區域顯示註冊／登入提示：沒有登入、訂閱、繞過或讀取受限制內容；只記錄公開分類名稱。沒有取得／使用 CrystalRoof 付費欄位、內部 API、網頁程式碼、圖片或商業算法。即使某些 transport 數字在公開頁面可見，本 app 也重新用 NaPTAN 及獨立距離計算，未複製其距離數字。

## 功能替代的限制

- Affluence → Census 教育／住屋統計 + 官方 IMD / 收入匯入接口；沒有憑空創造富裕分數。
- Reviews → 本地私人觀察，沒有政府提供的「居民評論」dataset。
- Noise → 真正 Defra WMS 模型值；不是以距離公路代替 dB。
- Environment → 水浸現行警報、planning zone、綠地、air adapter 分開；不是合成風險分數。
- Schools → DfE 開放資料與 admission 官方連結；沒有推論 catchment。
- Transport → 站點與距離、TfL 可支援的旅程；全英時間／票價交回官方旅程 planner。

每項資料來源、授權、需要 key 的項目及 fallback 請見 SOURCES.md 和 README。
