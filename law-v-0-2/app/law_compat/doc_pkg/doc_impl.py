import base64
import io
import os
from enum import Enum

import chardet
import fitz
import magic
import pdfplumber  # PyMuPDF
import requests
from bs4 import BeautifulSoup
from docx import Document
from striprtf.striprtf import rtf_to_text

from law_compat.text_utils import normalize_whitespace
from .minio_client import (
    is_s3_path, 
    download_from_minio, 
    cleanup_temp_file
)

OCR_SERVICE_URL = os.getenv("OCR_SERVICE_URL", "http://ocr:80/api/ocr")

class DocType(Enum):

    DOC_OLE = 0
    DOC = 1
    DOCX = 2
    TXT = 3
    PDF_TEXT = 4
    PDF_IMAGE = 5
    HTML = 7
    XLSX = 8
    XLS = 9
    CSV = 10
    RTF = 11
    UNKNOWN = -1


import platform
import subprocess

from docx import Document


def convert_doc(doc_path, output_directory, dst_type="txt"):
    system = platform.system()

    if system == "Darwin":  # macOS
        convert_command = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "--headless",
            "--convert-to",
            dst_type,
            "--outdir",
            output_directory,
            doc_path,
        ]
        print(convert_command)
    elif system == "Linux":
        convert_command = ["libreoffice", "--headless", "--convert-to", "txt", "--outdir", output_directory, doc_path]
    else:
        raise OSError(f"Unsupported OS: {system}")

    result = subprocess.run(convert_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in result.stdout.splitlines():
        print(line)
    # 检查命令执行状态
    if result.returncode != 0:
        print(f"命令执行失败，返回码: {result.returncode}")


def is_text_based_pdf(data: bytes):
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        for page in doc:
            if page.get_text():  # 尝试提取文本
                return True  # 如果能成功提取文本，则为文字型
        return False  # 无法提取文本，可能是图片型
    except Exception as e:
        print(f"Error opening file: {e}")
        return False


def detect_file_type(file_path):
    with open(file_path, "rb") as f:
        return detect_file_type_by_content(f.read())

def detect_file_type_by_content(data: bytes):
    file_type = magic.from_buffer(data, mime=True)
    if "msword" in file_type:
        return DocType.DOC
    elif "vnd.ms-word" in file_type or "application/x-ole-storage" in file_type or "application/CDFV" in file_type:
        return DocType.DOC_OLE
    elif (
        "vnd.openxmlformats-officedocument.wordprocessingml.document" in file_type
        or "application/octet-stream" in file_type
    ):
        return DocType.DOCX
    elif "plain" in file_type:
        return DocType.TXT
    elif "markdown" in file_type:
        return DocType.TXT
    elif "pdf" in file_type:
        return is_text_based_pdf(data) and DocType.PDF_TEXT or DocType.PDF_IMAGE
    elif "html" in file_type:
        return DocType.HTML
    elif "vnd.openxmlformats-officedocument.spreadsheetml.sheet" in file_type:
        return DocType.XLSX
    elif "vnd.ms-excel" in file_type or "application/vnd.ms-excel" in file_type:
        return DocType.XLS
    elif "csv" in file_type:
        return DocType.CSV
    elif "rtf" in file_type:
        return DocType.RTF
    elif "xml" in file_type:
        return DocType.HTML
    elif "zip" in file_type:
        return DocType.DOCX
    else:
        print(f"Unknown file type: {file_type}")
        return DocType.UNKNOWN

def read_docx(filename):
    doc = Document(filename)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return "\n".join(full_text)


#'application/octet-stream'
# read_docx('/Users/zhangfan/work/省厅/data/工作制度/1.2审计工作制度/浙江省公安厅机关采购合同管理办法.docx')
def read_html(filename):
    # 先读取文件的前一部分，以检测编码
    with open(filename, "rb") as file:
        raw_data = file.read(1000)  # 取头部一定量的数据来检测编码
        # 使用 chardet 检测文件编码
        result = chardet.detect(raw_data)
        encoding = result["encoding"]

    # 读取 HTML 文件
    with open(filename, "r", encoding=encoding) as file:
        html_content = file.read()
        # 创建 BeautifulSoup 对象并指定解析器
        soup = BeautifulSoup(html_content, "lxml")

        # 获取文档中的纯文本
        text = soup.get_text(separator=" ", strip=True)

    return text

def read_rtf(filename):
    with open(filename, 'r', errors='ignore') as f:
        rtf_content = f.read()
    
    text = rtf_to_text(rtf_content)
    return text

def read_image_pdf(filename, ocr_service_url):
    pdf_document = fitz.open(filename)
    text = ""
    page_number = 0
    for page in pdf_document:
        page_number += 1
        pixmap = page.get_pixmap()
        image_bytes = pixmap.tobytes(output="jpg")
        if ocr_service_url is None:
            import pytesseract
            from PIL import Image
            image = Image.open(io.BytesIO(image_bytes))
            text += pytesseract.image_to_string(image, lang="chi_sim+eng")
        else:
            # 使用ocr服务识别
            base64_image = base64.b64encode(image_bytes).decode("utf-8")
            response = requests.post(ocr_service_url, json={"imgBase64": base64_image})
            if response.status_code == 200:
                ocr_result = response.json()
                # 处理OCR结果
                text += ocr_result.get("result", "")
            else:
                print(f"Error: {response.status_code}, {response.text}")

    return text


def read_text_file(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return f.read()

def remove_garbled_content(text):
    """
    清洗文本，移除乱码和无关的技术路径
    """
    if not text:
        return text
        
    # 定义遇到即截断的关键字
    stop_markers = ("docProps", "MERGEFORMAT")
    
    cleaned_lines = []
    # 使用 keepends=True 保留原始换行符
    for line in text.splitlines(keepends=True):
        # 快速跳过空行
        if not line.strip():
            cleaned_lines.append(line)
            continue
            
        # 如果当前行包含任何停止标记，则丢弃该行及后续所有内容
        if any(marker in line for marker in stop_markers):
            break
            
        cleaned_lines.append(line)
        
    return "".join(cleaned_lines)

def read_file_content(filename, ocr_service_url=None, tika_service_url=None):
    """
    读取文件内容，支持本地文件和MinIO S3路径
    
    Args:
        filename: 文件路径，支持本地路径或s3://bucket/key格式
        ocr_service_url: OCR服务URL
        tika_service_url: Tika服务URL
    
    Returns:
        str: 文件内容文本
    """
    temp_file_path = None
    
    try:
        # 检查是否为S3路径
        if is_s3_path(filename):
            print(f"从MinIO下载文件: {filename}")
            temp_file_path = download_from_minio(filename)
            actual_filename = temp_file_path
        else:
            actual_filename = filename
        
        tika_service_url = os.getenv("TIKA_SERVICE_URL", "http://tika:9998") if tika_service_url is None else tika_service_url
        ocr_service_url = os.getenv("OCR_SERVICE_URL", "http://ocr:80/api/ocr") if ocr_service_url is None else ocr_service_url
        file_type = detect_file_type(actual_filename)
        text = ''
        
        if file_type == DocType.DOC_OLE or file_type == DocType.PDF_TEXT or file_type == DocType.DOCX or file_type == DocType.DOC or file_type == DocType.HTML:
            from tika import parser
            try:
                parsed = parser.from_file(actual_filename, serverEndpoint=tika_service_url, requestOptions={"timeout": 180000})
                text = remove_garbled_content(parsed["content"])
            except Exception as e:
                print(f"Error converting DOC: {e}")
                raise e
        elif file_type == DocType.DOCX or file_type == DocType.DOC:
            text = read_docx(actual_filename)
        elif file_type == DocType.TXT:
            text = read_text_file(actual_filename)
        elif file_type == DocType.PDF_IMAGE:
            text = read_image_pdf(actual_filename, ocr_service_url)
        elif file_type == DocType.HTML:
            text = read_html(actual_filename)
        elif file_type == DocType.RTF:
            text = read_rtf(actual_filename)
        else:
            raise ValueError(f"Unsupported file format {file_type}")
        
        # 替换特殊空格字符
        text = normalize_whitespace(text)
       
        return text
        
    finally:
        # 清理临时文件
        if temp_file_path:
            cleanup_temp_file(temp_file_path)
