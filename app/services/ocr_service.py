import json
import os
from pathlib import Path

import requests
import time

from loguru import logger

from core.config import settings




class OcrService:
    def __init__(self):
        self.api_url = settings.ocr_api_url
        self.api_key = settings.ocr_api_key
        self.model = settings.ocr_model
        self.optional_payload = {
            "markdownIgnoreLabels": [
                "header",
                "header_image",
                "footer",
                "footer_image",
                "number",
                "footnote",
                "aside_text"
            ],
            "useDocOrientationClassify": False,
            "useDocUnwarping": False,
            "useLayoutDetection": True,
            "useChartRecognition": False,
            "useSealRecognition": True,
            "useOcrForImageBlock": False,
            "mergeTables": True,
            "relevelTitles": True,
            "layoutShapeMode": "auto",
            "promptLabel": "ocr",
            "repetitionPenalty": 1,
            "temperature": 0,
            "topP": 1,
            "minPixels": 147384,
            "maxPixels": 2822400,
            "layoutNms": True,
            "restructurePages": True
        }

    def ocr(self, path: Path):
        file_path = path.as_posix()
        job_response = None
        logger.info(f"Processing file: {file_path}")
        headers = {
            "Authorization": f"bearer {self.api_key}",
        }
        real_file_name = self.get_file_name(file_path)
        if file_path.startswith("http"):
            # 文件是下载链接
            headers["Content-Type"] = "application/json"
            payload = {
                "fileUrl": file_path,
                "model": self.model,
                "optionalPayload": self.optional_payload
            }
            job_response = requests.post(self.api_url, json=payload, headers=headers)
        else:
            # 本地文件
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"上传文件未找到: {file_path}")

            data = {
                "model": self.model,
                "optionalPayload": json.dumps(self.optional_payload)
            }

            with open(file_path, "rb") as f:
                files = {"file": f}
                job_response = requests.post(self.api_url, headers=headers, data=data, files=files)

        logger.info(f"请求OCR模型，状态码: {job_response.status_code}")
        if job_response.status_code != 200:
            logger.warning(f"请求OCR模型异常，返回text: {job_response.text}")
            raise Exception(f"请求OCR模型异常")
        logger.info("job_response: {}", job_response.json())
        job_id = job_response.json()["data"]["jobId"]
        logger.info(f"Job submitted successfully. job id: {job_id}, Start polling for results")

        while True:
            # 轮询请求ocr结果
            job_result_response = requests.get(f"{self.api_url}/{job_id}", headers=headers)
            assert job_result_response.status_code == 200
            state = job_result_response.json()["data"]["state"]
            if state == 'pending':
                logger.info("The current status of the job is pending")
            elif state == 'running':
                try:
                    total_pages = job_result_response.json()['data']['extractProgress']['totalPages']
                    extracted_pages = job_result_response.json()['data']['extractProgress']['extractedPages']
                    logger.info(
                        f"The current status of the job is running, total pages: {total_pages}, extracted pages: {extracted_pages}")
                except KeyError:
                    logger.info("The current status of the job is running...")
                # 等五秒再轮询
                time.sleep(5)
            elif state == 'done':
                extracted_pages = job_result_response.json()['data']['extractProgress']['extractedPages']
                start_time = job_result_response.json()['data']['extractProgress']['startTime']
                end_time = job_result_response.json()['data']['extractProgress']['endTime']
                logger.info(
                    f"Job completed, successfully extracted pages: {extracted_pages}, start time: {start_time}, end time: {end_time}")
                jsonl_url = job_result_response.json()['data']['resultUrl']['jsonUrl']
                logger.info(f"OCR识别已完成，jsonUrl={jsonl_url}")
                break
            elif state == "failed":
                error_msg = job_result_response.json()['data']['errorMsg']
                logger.warning(f"Job failed, failure reason：{error_msg}")
                raise Exception(f"OCR扫描失败：{error_msg}")

        if not jsonl_url:
            logger.warning("OCR结果为空")
            raise Exception("OCR扫描失败,原因：OCR识别为空")
        else:
            jsonl_response = requests.get(jsonl_url)
            jsonl_response.raise_for_status()
            lines = jsonl_response.text.strip().split('\n')
            output_dir = settings.upload_dir
            os.makedirs(output_dir, exist_ok=True)
            page_num = 0
            md_all_path = os.path.join(output_dir, real_file_name + "_ocr_result.md")
            # 记录识别后的md全文
            md_content = ""
            with open(md_all_path, "w", encoding="utf-8") as md_all_file:
                for line_num, line in enumerate(lines, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    result = json.loads(line)["result"]
                    for i, res in enumerate(result["layoutParsingResults"]):
                        # 将 Markdown 文本追加写入总文件
                        # 可以加上可选的分隔标记，避免内容粘连
                        separator = "\n\n---\n\n" if page_num > 0 else ""  # 分隔不同页面
                        md_all_file.write(separator + res["markdown"]["text"])
                        md_content += separator + res["markdown"]["text"]

                        # 图片保存逻辑保持不变（markdown images）
                        for img_path, img in res["markdown"]["images"].items():
                            full_img_path = os.path.join(output_dir, img_path)
                            os.makedirs(os.path.dirname(full_img_path), exist_ok=True)
                            img_bytes = requests.get(img).content
                            with open(full_img_path, "wb") as img_file:
                                img_file.write(img_bytes)
                            logger.info(f"OCR得到的图片[images]保存至: {full_img_path}")

                        page_num += 1

            logger.info(f"OCR识别后的Markdown已存储至 {md_all_path}")
            return md_content

    @staticmethod
    def get_file_name(file_path: str):
        if file_path.startswith("http"):
            # URL 情况：取最后一个 '/' 后的部分，再去掉查询参数和扩展名
            base_name = file_path.rsplit('/', 1)[-1].split('?')[0]
        else:
            base_name = os.path.basename(file_path)
        # 去掉扩展名（如 .pdf .png .jpg 等）
        return os.path.splitext(base_name)[0]

ocr_service = OcrService()