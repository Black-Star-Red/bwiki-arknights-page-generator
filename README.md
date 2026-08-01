# bwiki-arknights-page-generator
用于自动生成明日方舟 Bwiki 页面内容的工具链，支持数据映射、模板渲染与批量产出


## 初始化
1. python -m venv .venv
2. 
    PowerShell：.\.venv\Scripts\Activate.ps1
    CMD：.\.venv\Scripts\activate.bat
1. pip install -r requirements.txt
2. pip install -e .

## 本地配置
1. 复制示例并改名：
   `config/config.local.example.json` → `config/config.local.json`
2. 填写 B 站 `cookies`；若要用数据库，把 `database.enabled` 设为 `true` 并改 `url`。


## 启动
1. python -m app.gui_main

## 数据源配置
1. 
   改配置：config/data_sources
   默认数据源路径：../ArknightsData/...
   