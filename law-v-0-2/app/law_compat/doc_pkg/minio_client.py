#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinIO客户端模块

提供MinIO文件操作功能，包括文件下载、路径解析等。
"""

import os
import tempfile
from datetime import datetime
import uuid
from typing import Tuple 
from botocore.exceptions import ClientError, NoCredentialsError


# MinIO配置
MINIO_HOST = os.getenv("MINIO_HOST", "localhost")
MINIO_PORT = os.getenv("MINIO_PORT", "9000")
MINIO_ENDPOINT = f"{MINIO_HOST}:{MINIO_PORT}"
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
if not MINIO_ACCESS_KEY:
    MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
if not MINIO_SECRET_KEY:
    MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "")
MINIO_USE_SSL = os.getenv("MINIO_USE_SSL", "false").lower() == "true"


def is_s3_path(path: str) -> bool:
    """
    检查是否为S3路径格式
    
    Args:
        path: 文件路径
        
    Returns:
        bool: 是否为S3路径
    """
    return path.startswith("s3://")


def parse_s3_path(s3_path: str) -> Tuple[str, str]:
    """
    解析S3路径，返回bucket和key
    
    Args:
        s3_path: S3路径，格式为 s3://bucket/key
        
    Returns:
        Tuple[str, str]: (bucket, key)
        
    Raises:
        ValueError: 当路径格式无效时
    """
    if not is_s3_path(s3_path):
        raise ValueError(f"Invalid S3 path: {s3_path}")
    
    # 移除s3://前缀
    path_without_prefix = s3_path[5:]
    
    # 分割bucket和key
    parts = path_without_prefix.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid S3 path format: {s3_path}")
    
    bucket = parts[0]
    key = parts[1]
    
    return bucket, key

def get_object_data(s3_path: str) -> bytes:
    """
    获取S3对象数据
    
    Args:
        s3_path: S3路径，格式为 s3://bucket/key
    """
    bucket, key = parse_s3_path(s3_path)
    s3_client = get_minio_client()
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response['Body'].read()

def download_from_minio(s3_path: str) -> str:
    """
    从MinIO下载文件到临时文件
    
    Args:
        s3_path: S3路径，格式为 s3://bucket/key
        
    Returns:
        str: 临时文件路径
        
    Raises:
        ImportError: 当boto3未安装时
        Exception: 当下载失败时
    """
    bucket, key = parse_s3_path(s3_path)
    
    # 创建S3客户端
    s3_client = get_minio_client()
    # 创建临时文件
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(key)[1])
    temp_file_path = temp_file.name
    temp_file.close()
    
    try:
        # 下载文件
        s3_client.download_file(bucket, key, temp_file_path)
        return temp_file_path
    except (ClientError, NoCredentialsError) as e:
        # 清理临时文件
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        raise Exception(f"Failed to download file from MinIO: {e}")
    except Exception as e:
        # 清理临时文件
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        raise e


def cleanup_temp_file(temp_file_path: str) -> None:
    """
    清理临时文件
    
    Args:
        temp_file_path: 临时文件路径
    """
    try:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
    except Exception as e:
        print(f"Warning: Failed to cleanup temp file {temp_file_path}: {e}")


def get_minio_client():
    """
    获取MinIO客户端实例
    
    Returns:
        boto3.client: S3客户端实例
        
    Raises:
        ImportError: 当boto3未安装时
    """
    try:
        import boto3
    except ImportError:
        raise ImportError("boto3 is required for MinIO support. Install with: uv add boto3")
    
    return boto3.client(
        's3',
        endpoint_url=f"http{'s' if MINIO_USE_SSL else ''}://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name='us-east-1'
    )


def list_buckets() -> list:
    """
    列出所有可用的bucket
    
    Returns:
        list: bucket名称列表
        
    Raises:
        Exception: 当连接失败时
    """
    try:
        s3_client = get_minio_client()
        response = s3_client.list_buckets()
        return [bucket['Name'] for bucket in response['Buckets']]
    except Exception as e:
        raise Exception(f"Failed to list buckets: {e}")


def list_objects(bucket: str, prefix: str = "") -> list:
    """
    列出指定bucket中的对象
    
    Args:
        bucket: bucket名称
        prefix: 对象前缀（可选）
        
    Returns:
        list: 对象key列表
        
    Raises:
        Exception: 当操作失败时
    """
    try:
        s3_client = get_minio_client()
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        return [obj['Key'] for obj in response.get('Contents', [])]
    except Exception as e:
        raise Exception(f"Failed to list objects in bucket {bucket}: {e}")

def list_objects_in_dir(s3_path: str) -> list:
    """
    列出指定目录中的对象
    
    Args:
        s3_path: S3路径，格式为 s3://bucket/dir

    Returns:
        list: 对象key列表
        
    Raises:
        Exception: 当操作失败时
    """
    bucket, key = parse_s3_path(s3_path)
    s3_client = get_minio_client()
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=key)
    return [f"s3://{bucket}/{obj['Key']}" for obj in response.get('Contents', [])]


def file_exists(s3_path: str) -> bool:
    """
    检查文件是否存在
    
    Args:
        s3_path: S3路径
        
    Returns:
        bool: 文件是否存在
    """
    try:
        bucket, key = parse_s3_path(s3_path)
        s3_client = get_minio_client()
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def get_file_size(s3_path: str) -> int:
    """
    获取文件大小
    
    Args:
        s3_path: S3路径
        
    Returns:
        int: 文件大小（字节）
        
    Raises:
        Exception: 当文件不存在或操作失败时
    """
    try:
        bucket, key = parse_s3_path(s3_path)
        s3_client = get_minio_client()
        response = s3_client.head_object(Bucket=bucket, Key=key)
        return response['ContentLength']
    except Exception as e:
        raise Exception(f"Failed to get file size for {s3_path}: {e}")


def get_file_info(s3_path: str) -> dict:
    """
    获取文件信息
    
    Args:
        s3_path: S3路径
        
    Returns:
        dict: 文件信息，包含大小、修改时间等
        
    Raises:
        Exception: 当文件不存在或操作失败时
    """
    try:
        bucket, key = parse_s3_path(s3_path)
        s3_client = get_minio_client()
        response = s3_client.head_object(Bucket=bucket, Key=key)
        
        return {
            'bucket': bucket,
            'key': key,
            'size': response['ContentLength'],
            'last_modified': response['LastModified'],
            'content_type': response.get('ContentType', ''),
            'etag': response.get('ETag', '')
        }
    except Exception as e:
        raise Exception(f"Failed to get file info for {s3_path}: {e}") 

def upload_file_to_s3(data: bytes, bucket: str, key: str = None, file_name: str = None) -> str:
    """
    上传文件到S3
    
    Args:
        data: 文件数据
        bucket: bucket名称
        key: 文件key 如果为空，则自动生成key
        file_name: 文件名 如果为空，则从key中获取扩展名
        
    Returns:
        str: S3路径
        
    Raises:
        Exception: 当上传失败时
    """
    # 从file_name中获取获取扩展名
    if file_name:
        extension = os.path.splitext(file_name)[1]
    elif key:
        extension = os.path.splitext(key)[1]
    else:
        extension = ""
    # 如果key为空，则自动生成key
    if key is None:
        # 默认为upload/年/月/日/uuid.extension
        key = f"upload/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4()}{extension}"
    # 上传文件
    s3_client = get_minio_client()
    s3_client.put_object(Bucket=bucket, Key=key, Body=data)
    # s3://bucket/key
    return f"s3://{bucket}/{key}"
