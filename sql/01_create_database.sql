-- 01_create_database.sql
-- PetCare 宠物店管理系统
-- 功能：创建数据库 PetCareDB

-- 如果数据库已存在，先删除，方便从空库复现
IF DB_ID('PetCareDB') IS NOT NULL
    DROP DATABASE PetCareDB;
GO

-- 创建数据库
CREATE DATABASE PetCareDB;
GO

-- 切换到新建的数据库
USE PetCareDB;
GO