-- --------------------------------------------------------
-- 主机:                           43.130.58.80
-- 服务器版本:                        10.6.18-MariaDB-0ubuntu0.22.04.1 - Ubuntu 22.04
-- 服务器操作系统:                      debian-linux-gnu
-- HeidiSQL 版本:                  12.0.0.6468
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

-- 导出  表 gaiabase.crawlUrlSubtask 结构
CREATE TABLE IF NOT EXISTS `crawlUrlSubtask` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `url_id` int(11) NOT NULL DEFAULT 0,
  `crawl_url` char(200) NOT NULL,
  `subtask_status` int(11) DEFAULT 0,
  `embed_status` int(11) DEFAULT 0,
  `upload_time` datetime DEFAULT current_timestamp(),
  `end_time` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`) USING BTREE,
  KEY `FK_crawlUrl_task` (`url_id`),
  CONSTRAINT `FK_crawlUrl_task` FOREIGN KEY (`url_id`) REFERENCES `urlSubtask` (`id`) ON DELETE CASCADE ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=583 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=DYNAMIC;

-- 数据导出被取消选择。

-- 导出  表 gaiabase.fileSubtask 结构
CREATE TABLE IF NOT EXISTS `fileSubtask` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `task_id` char(200) NOT NULL,
  `file_name` char(200) NOT NULL,
  `subtask_status` int(11) DEFAULT 0,
  `embed_status` int(11) DEFAULT 0,
  `upload_time` datetime DEFAULT current_timestamp(),
  `end_time` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `word_count` int(11) DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `FK_file_task` (`task_id`),
  CONSTRAINT `FK_file_task` FOREIGN KEY (`task_id`) REFERENCES `task` (`task_id`) ON DELETE CASCADE ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=3374 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

-- 数据导出被取消选择。

-- 导出  表 gaiabase.QASubtask 结构
CREATE TABLE IF NOT EXISTS `QASubtask` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `task_id` char(200) NOT NULL,
  `question` longtext NOT NULL,
  `answer` longtext NOT NULL,
  `embed_status` int(11) DEFAULT 0,
  `upload_time` datetime DEFAULT current_timestamp(),
  `end_time` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`) USING BTREE,
  KEY `FK_task` (`task_id`) USING BTREE,
  CONSTRAINT `FK_QA_task` FOREIGN KEY (`task_id`) REFERENCES `task` (`task_id`) ON DELETE CASCADE ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=156 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=DYNAMIC;

-- 数据导出被取消选择。

-- 导出  表 gaiabase.task 结构
CREATE TABLE IF NOT EXISTS `task` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `task_id` char(200) NOT NULL,
  `task_status` int(11) DEFAULT 0,
  `start_time` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `task_id_UNIQUE` (`task_id`),
  KEY `task_id` (`task_id`)
) ENGINE=InnoDB AUTO_INCREMENT=328 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

-- 数据导出被取消选择。

-- 导出  表 gaiabase.urlSubtask 结构
CREATE TABLE IF NOT EXISTS `urlSubtask` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `task_id` char(200) NOT NULL,
  `url` char(200) NOT NULL,
  `subtask_status` int(11) DEFAULT 0,
  `embed_status` int(11) DEFAULT 0,
  `upload_time` datetime DEFAULT current_timestamp(),
  `end_time` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`) USING BTREE,
  KEY `FK__task` (`task_id`) USING BTREE,
  CONSTRAINT `FK_url_task` FOREIGN KEY (`task_id`) REFERENCES `task` (`task_id`) ON DELETE CASCADE ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=41 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=DYNAMIC;

-- 数据导出被取消选择。

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
