# 项目运行指南

按照以下步骤来运行项目：

## 步骤 1: 安装依赖

首先，使用`pip`安装项目所需的依赖：

```bash
pip install -r requirements.txt
```

## 步骤 2: 安装 LibreOffice 和 MariaDB 开发库

使用`apt-get`更新系统并安装`MariaDB`开发库和`LibreOffice`：

```bash
sudo apt-get update
sudo apt-get install libmariadb-dev
sudo apt install libreoffice
```

## 步骤 3: 创建环境变量文件

创建一个`.env`文件并填写所需的环境变量。文件应包含如数据库连接等配置信息。

```dotenv
LLAMA_CLOUD_API_KEY=XXX
FIRECRAWL_KEY=XXX
MYSQL_HOST=XXX
MYSQL_USERNAME=XXX
MYSQL_PASSWORD=XXX
MYSQL_DATABASE_NAME=XXX
```

## 步骤 4: 启动`Web`服务器

创建一个`.env`文件并填写所需的环境变量。文件应包含如数据库连接等配置信息。

```bash
python3 webserver.py
```

按照这些步骤操作后，项目应该能够正常运行。