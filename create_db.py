import json
import os
import time

import mysql.connector as mysql
import requests
from dotenv import load_dotenv

from db_access import DBAccess

generate_script = """
-- MySQL Workbench Forward Engineering

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- -----------------------------------------------------
-- Schema hfc_db
-- -----------------------------------------------------
DROP SCHEMA IF EXISTS `hfc_db` ;

-- -----------------------------------------------------
-- Schema hfc_db
-- -----------------------------------------------------
CREATE SCHEMA IF NOT EXISTS `hfc_db` DEFAULT CHARACTER SET utf8 ;
USE `hfc_db` ;

-- -----------------------------------------------------
-- Table `hfc_db`.`areas`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `hfc_db`.`areas` ;

CREATE TABLE IF NOT EXISTS `hfc_db`.`areas` (
  `area_id` INT NOT NULL,
  `area_name` VARCHAR(64) NOT NULL,
  PRIMARY KEY (`area_id`),
  UNIQUE INDEX `area_id_UNIQUE` (`area_id` ASC) VISIBLE)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `hfc_db`.`districts`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `hfc_db`.`districts` ;

CREATE TABLE IF NOT EXISTS `hfc_db`.`districts` (
  `district_id` INT NOT NULL,
  `district_name` VARCHAR(64) NOT NULL,
  `area_id` INT NOT NULL,
  `migun_time` INT NULL,
  PRIMARY KEY (`district_id`),
  UNIQUE INDEX `area_code_UNIQUE` (`district_id` ASC) VISIBLE,
  INDEX `area_id_idx` (`area_id` ASC) VISIBLE,
  CONSTRAINT `area_id`
    FOREIGN KEY (`area_id`)
    REFERENCES `hfc_db`.`areas` (`area_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `hfc_db`.`servers`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `hfc_db`.`servers` ;

CREATE TABLE IF NOT EXISTS `hfc_db`.`servers` (
  `server_id` BIGINT(8) UNSIGNED NOT NULL,
  `server_lang` VARCHAR(15) NOT NULL,
  PRIMARY KEY (`server_id`),
  UNIQUE INDEX `idservers_UNIQUE` (`server_id` ASC) VISIBLE)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `hfc_db`.`channels`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `hfc_db`.`channels` ;

CREATE TABLE IF NOT EXISTS `hfc_db`.`channels` (
  `channel_id` BIGINT(8) UNSIGNED NOT NULL,
  `server_id` BIGINT(8) UNSIGNED NULL,
  `channel_lang` VARCHAR(15) NOT NULL,
  PRIMARY KEY (`channel_id`),
  UNIQUE INDEX `channel_id_UNIQUE` (`channel_id` ASC) VISIBLE,
  CONSTRAINT `server_id`
    FOREIGN KEY (`server_id`)
    REFERENCES `hfc_db`.`servers` (`server_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;

USE `hfc_db`;

DELIMITER $$

USE `hfc_db`$$
DROP TRIGGER IF EXISTS `hfc_db`.`channels_BEFORE_INSERT` $$
USE `hfc_db`$$
CREATE DEFINER = CURRENT_USER TRIGGER `hfc_db`.`channels_BEFORE_INSERT` BEFORE INSERT ON `channels` FOR EACH ROW
BEGIN

  DECLARE server_lang VARCHAR(15);
  
  -- Get the server_lang for the corresponding server_id
  SELECT server_lang INTO server_lang
  FROM servers
  WHERE server_id = NEW.server_id;
  
  -- Set channel_lang to server_lang if it's NULL
  IF NEW.channel_lang IS NULL THEN
    SET NEW.channel_lang = IFNULL(server_lang, 'he');
  END IF;
END$$

DELIMITER ;

SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;

"""

load_dotenv()
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')

db = mysql.connect(
    host='localhost',
    user=DB_USERNAME,
    password=DB_PASSWORD
)

crsr = db.cursor()
crsr.execute(generate_script)
crsr.fetchall()
print(crsr.warnings)
db.close()

districts: list[dict] = json.loads(requests.get('https://www.oref.org.il//Shared/Ajax/GetDistricts.aspx?lang=he').text)

db = DBAccess()
for district in districts:
    db.add_district(
        district["id"],
        district["label"],
        district["areaid"],
        district["areaname"],
        district["migun_time"]
    )

db.add_district(99999, 'בדיקה', 999, 'בדיקה', 600)

db.connection.commit()