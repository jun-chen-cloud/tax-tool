# -*- coding: utf-8 -*-
import streamlit as st
import sys
import os
import time
import random
import json
import requests
import base64
import uuid
import logging
from datetime import datetime, timedelta
import warnings
import ddddocr
from PIL import Image, ImageFilter
from io import BytesIO

warnings.filterwarnings("ignore")
requests.packages.urllib3.disable_warnings()

os.environ.update({
    "PYTHONIOENCODING": "utf-8",
    "LC_ALL": "zh_CN.UTF-8",
    "LANG": "zh_CN.UTF-8"
})

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# -------------------------- 全国36省级行政区完整映射 --------------------------
class CreditCodeProvince:
    PROVINCE_MAP = {
        '11': '北京市', '12': '天津市', '13': '河北省', '14': '山西省', '15': '内蒙古自治区',
        '21': '辽宁省', '22': '吉林省', '23': '黑龙江省',
        '31': '上海市', '32': '江苏省', '33': '浙江省', '34': '安徽省', '35': '福建省', '36': '江西省', '37': '山东省',
        '41': '河南省', '42': '湖北省', '43': '湖南省',
        '44': '广东省', '45': '广西壮族自治区', '46': '海南省',
        '50': '重庆市', '51': '四川省', '52': '贵州省', '53': '云南省', '54': '西藏自治区',
        '61': '陕西省', '62': '甘肃省', '63': '青海省', '64': '宁夏回族自治区', '65': '新疆维吾尔自治区',
        '71': '台湾省', '81': '香港特别行政区', '82': '澳门特别行政区'
    }
    @classmethod
    def get_province_from_credit_code(cls, credit_code):
        if not credit_code or len(credit_code) != 18:
            raise ValueError("信用代码长度必须为18位")
        city_code = credit_code[2:6]
        if city_code == '4403':
            return '深圳市'
        province_code = credit_code[2:4]
        return cls.PROVINCE_MAP.get(province_code, None)

# -------------------------- 全国税务接口完整配置 --------------------------
PROVINCE_TAX_API_CONFIG = {
    '北京市': {'base_url': 'https://etax.beijing.chinatax.gov.cn:8443', 'status': 'stable'},
    '天津市': {'base_url': 'https://etax.tianjin.chinatax.gov.cn:8443', 'status': 'stable'},
    '河北省': {'base_url': 'https://etax.hebei.chinatax.gov.cn:8443', 'status': 'stable'},
    '山西省': {'base_url': 'https://etax.shanxi.chinatax.gov.cn:8443', 'status': 'test'},
    '内蒙古自治区': {'base_url': 'https://etax.neimenggu.chinatax.gov.cn:8443', 'status': 'test'},
    '辽宁省': {'base_url': 'https://etax.liaoning.chinatax.gov.cn:8443', 'status': 'test'},
    '吉林省': {'base_url': 'https://etax.jilin.chinatax.gov.cn:8443', 'status': 'test'},
    '黑龙江省': {'base_url': 'https://etax.heilongjiang.chinatax.gov.cn:8443', 'status': 'test'},
    '上海市': {'base_url': 'https://etax.shanghai.chinatax.gov.cn:8443', 'status': 'stable'},
    '江苏省': {'base_url': 'https://etax.jiangsu.chinatax.gov.cn:8443', 'status': 'stable'},
    '浙江省': {'base_url': 'https://etax.zhejiang.chinatax.gov.cn:8443', 'status': 'stable'},
    '安徽省': {'base_url': 'https://etax.anhui.chinatax.gov.cn:8443', 'status': 'stable'},
    '福建省': {'base_url': 'https://etax.fujian.chinatax.gov.cn:8443', 'status': 'stable'},
    '江西省': {'base_url': 'https://etax.jiangxi.chinatax.gov.cn:8443', 'status': 'test'},
    '山东省': {'base_url': 'https://etax.shandong.chinatax.gov.cn:8443', 'status': 'test'},
    '河南省': {'base_url': 'https://etax.henan.chinatax.gov.cn:8443', 'status': 'test'},
    '湖北省': {'base_url': 'https://etax.hubei.chinatax.gov.cn:8443', 'status': 'stable'},
    '湖南省': {'base_url': 'https://etax.hunan.chinatax.gov.cn:8443', 'status': 'test'},
    '广东省': {'base_url': 'https://etax.guangdong.chinatax.gov.cn:8443', 'status': 'stable'},
    '深圳市': {'base_url': 'https://etax.shenzhen.chinatax.gov.cn:8443', 'status': 'stable'},
    '广西壮族自治区': {'base_url': 'https://etax.guangxi.chinatax.gov.cn:8443', 'status': 'test'},
    '海南省': {'base_url': 'https://etax.hainan.chinatax.gov.cn:8443', 'status': 'test'},
    '重庆市': {'base_url': 'https://etax.chongqing.chinatax.gov.cn:8443', 'status': 'stable'},
    '四川省': {'base_url': 'https://etax.sichuan.chinatax.gov.cn:8443', 'status': 'test'},
    '贵州省': {'base_url': 'https://etax.guizhou.chinatax.gov.cn:8443', 'status': 'stable'},
    '云南省': {'base_url': 'https://etax.yunnan.chinatax.gov.cn', 'status': 'stable'},
    '西藏自治区': {'base_url': 'https://etax.xizang.chinatax.gov.cn:8443', 'status': 'test'},
    '陕西省': {'base_url': 'https://etax.shaanxi.chinatax.gov.cn:8443', 'status': 'test'},
    '甘肃省': {'base_url': 'https://etax.gansu.chinatax.gov.cn:8443', 'status': 'stable'},
    '青海省': {'base_url': 'https://etax.qinghai.chinatax.gov.cn:8443', 'status': 'stable'},
    '宁夏回族自治区': {'base_url': 'https://etax.ningxia.chinatax.gov.cn:8443', 'status': 'stable'},
    '新疆维吾尔自治区': {'base_url': 'https://etax.xinjiang.chinatax.gov.cn:8443', 'status': 'test'},
    '台湾省': {'base_url': 'https://etax.taiwan.chinatax.gov.cn:8443', 'status': 'unavailable'},
    '香港特别行政区': {'base_url': 'https://etax.hongkong.chinatax.gov.cn:8443', 'status': 'unavailable'},
    '澳门特别行政区': {'base_url': 'https://etax.macao.chinatax.gov.cn:8443', 'status': 'unavailable'}
}

STABLE_PROVINCES = [p for p, cfg in PROVINCE_TAX_API_CONFIG.items() if cfg['status'] == 'stable']
TEST_PROVINCES = [p for p, cfg in PROVINCE_TAX_API_CONFIG.items() if cfg['status'] == 'test']
UNAVAILABLE_PROVINCES = [p for p, cfg in PROVINCE_TAX_API_CONFIG.items() if cfg['status'] == 'unavailable']

TAXPAYER_QUERY_CACHE = {}
CACHE_EXPIRY_TIME = 3600

# ===================== 双OCR模型并行，识别率翻倍 =====================
ocr_normal = ddddocr.DdddOcr(show_ad=False, beta=False)  # 标准版
ocr_beta = ddddocr.DdddOcr(show_ad=False, beta=True)     # 增强版

# ===================== 8套梯度预处理模板（含形态学，破解粘连/残缺） =====================
def pre_1_default(img_bytes):
    """模板1：标准通用"""
    img = Image.open(BytesIO(img_bytes)).convert('L')
    img = img.point(lambda x: 0 if x < 135 else 255)
    img = img.filter(ImageFilter.MedianFilter(1))
    img = img.filter(ImageFilter.SHARPEN)
    return img.resize((100, 32))

def pre_2_low_thresh(img_bytes):
    """模板2：低阈值，适配深色扭曲字符"""
    img = Image.open(BytesIO(img_bytes)).convert('L')
    img = img.point(lambda x: 0 if x < 115 else 255)
    img = img.filter(ImageFilter.MedianFilter(1))
    img = img.filter(ImageFilter.SHARPEN)
    return img.resize((100, 32))

def pre_3_high_thresh(img_bytes):
    """模板3：高阈值，适配浅色噪点多字符"""
    img = Image.open(BytesIO(img_bytes)).convert('L')
    img = img.point(lambda x: 0 if x < 145 else 255)
    img = img.filter(ImageFilter.MedianFilter(1))
    img = img.filter(ImageFilter.SHARPEN)
    return img.resize((100, 32))

def pre_4_erosion(img_bytes):
    """模板4：腐蚀（去粘连、断开笔画）"""
    img = Image.open(BytesIO(img_bytes)).convert('L')
    img = img.point(lambda x: 0 if x < 130 else 255)
    img = img.filter(ImageFilter.MinFilter(1))  # 腐蚀
    img = img.filter(ImageFilter.SHARPEN)
    return img.resize((100, 32))

def pre_5_dilate(img_bytes):
    """模板5：膨胀（补残缺笔画）"""
    img = Image.open(BytesIO(img_bytes)).convert('L')
    img = img.point(lambda x: 0 if x < 130 else 255)
    img = img.filter(ImageFilter.MaxFilter(1))  # 膨胀
    img = img.filter(ImageFilter.SHARPEN)
    return img.resize((100, 32))

def pre_6_open(img_bytes):
    """模板6：开运算（先腐蚀后膨胀，去噪保形状）"""
    img = Image.open(BytesIO(img_bytes)).convert('L')
    img = img.point(lambda x: 0 if x < 130 else 255)
    img = img.filter(ImageFilter.MinFilter(1))
    img = img.filter(ImageFilter.MaxFilter(1))
    img = img.filter(ImageFilter.SHARPEN)
    return img.resize((100, 32))

def pre_7_hubei(img_bytes):
    """模板7：湖北专属（适配高度紧凑扭曲）"""
    img = Image.open(BytesIO(img_bytes)).convert('L')
    img = img.point(lambda x: 0 if x < 110 else 255)
    img = img.filter(ImageFilter.MinFilter(1))
    img = img.filter(ImageFilter.SHARPEN)
    return img.resize((120, 36))

def pre_8_fujian(img_bytes):
    """模板8：福建专属（适配模糊低对比）"""
    img = Image.open(BytesIO(img_bytes)).convert('L')
    img = img.point(lambda x: 0 if x < 140 else 255)
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    img = img.filter(ImageFilter.MaxFilter(1))
    img = img.filter(ImageFilter.SHARPEN)
    return img.resize((100, 32))

# 省份专属模板池
PROVINCE_PREPROCESS_MAP = {
    '湖北省': [pre_7_hubei, pre_4_erosion, pre_6_open, pre_2_low_thresh, pre_1_default],
    '福建省': [pre_8_fujian, pre_5_dilate, pre_3_high_thresh, pre_6_open, pre_1_default],
    '广东省': [pre_1_default, pre_4_erosion, pre_2_low_thresh],
    '深圳市': [pre_1_default, pre_4_erosion, pre_2_low_thresh],
    'default': [pre_1_default, pre_2_low_thresh, pre_3_high_thresh, pre_4_erosion, pre_5_dilate, pre_6_open]
}

# ===================== 【严格原生识别：双模型+全模板轮询，必须4位才返回，绝不补位】 =====================
def recognize_captcha(captcha_image, province='default'):
    try:
        if 'base64,' in captcha_image:
            img_data = captcha_image.split('base64,')[1]
        else:
            img_data = captcha_image.strip()

        img_bytes = base64.b64decode(img_data)
        pre_funcs = PROVINCE_PREPROCESS_MAP.get(province, PROVINCE_PREPROCESS_MAP['default'])

        # 遍历所有预处理模板
        for pre_func in pre_funcs:
            processed_img = pre_func(img_bytes)
            buf = BytesIO()
            processed_img.save(buf, format='PNG')
            img_bin = buf.getvalue()

            # 双模型识别
            raw_normal = ocr_normal.classification(img_bin)
            raw_beta = ocr_beta.classification(img_bin)

            # 严格过滤：仅保留字母+数字，剔除中文/符号/空格
            clean_normal = ''.join(c for c in raw_normal if c.isalnum() and not '\u4e00' <= c <= '\u9fff')
            clean_beta = ''.join(c for c in raw_beta if c.isalnum() and not '\u4e00' <= c <= '\u9fff')

            logger.info(f"[{province}] 模板{pre_func.__name__} | 标准版:{clean_normal} | 增强版:{clean_beta}")

            # 任意一个模型识别出4位，直接返回
            if len(clean_normal) == 4:
                logger.info(f"✅ [{province}] 标准版原生识别成功: {clean_normal}")
                return clean_normal
            if len(clean_beta) == 4:
                logger.info(f"✅ [{province}] 增强版原生识别成功: {clean_beta}")
                return clean_beta

        # 所有模板+双模型都识别不到4位 → 刷新验证码
        logger.warning(f"[{province}] 全模板+双模型均未识别到4位有效字符，刷新验证码")
        return None

    except Exception as e:
        logger.warning(f"[{province}] 识别异常: {str(e)}，刷新验证码")
        return None

# -------------------------- 工具函数 --------------------------
def get_optimized_headers(base_url):
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    ]
    return {
        "User-Agent": random.choice(ua_list),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Origin": base_url,
        "Referer": f"{base_url}/xxbg/view/zhsffw/",
        "requestid": str(int(time.time() * 1000)) + str(random.randint(100,999)),
        "x-b3-traceid": str(uuid.uuid4()).replace("-", ""),
        "Cache-Control": "no-cache"
    }

def get_query_provinces(nsrsbh):
    provinces = []
    try:
        main_province = CreditCodeProvince.get_province_from_credit_code(nsrsbh)
        if main_province and main_province not in UNAVAILABLE_PROVINCES:
            provinces.append(main_province)
    except Exception as e:
        logger.warning(f"省份识别异常: {e}")
    backup_provinces = [p for p in STABLE_PROVINCES if p not in provinces]
    random.shuffle(backup_provinces)
    provinces.extend(backup_provinces[:3])
    return provinces

def get_cached_result(nsrsbh):
    if nsrsbh in TAXPAYER_QUERY_CACHE:
        entry = TAXPAYER_QUERY_CACHE[nsrsbh]
        if time.time() - entry["timestamp"] < CACHE_EXPIRY_TIME:
            return entry["result"]
        del TAXPAYER_QUERY_CACHE[nsrsbh]
    return None

def cache_result(nsrsbh, result):
    TAXPAYER_QUERY_CACHE[nsrsbh] = {"result": result, "timestamp": time.time()}

# -------------------------- 核心查询逻辑 --------------------------
def query_taxpayer_status(nsrsbh):
    cached = get_cached_result(nsrsbh)
    if cached:
        logger.info(f"{nsrsbh} 使用缓存结果")
        return cached
    results = []
    start_time = time.time()
    query_provinces = get_query_provinces(nsrsbh)
    if not query_provinces:
        results.append(f"信用代码：{nsrsbh}")
        results.append("❌ 无可查询省份（港澳台暂不支持）")
        results.append("="*50)
        cache_result(nsrsbh, results)
        return results
    results.append(f"信用代码：{nsrsbh}")
    results.append(f"🔍 查询计划：{', '.join(query_provinces)}")
    results.append("")
    max_retries_per_province = 15  # 放宽重试次数，给全量轮询充足时间
    success = False

    for query_prov in query_provinces:
        base_url = PROVINCE_TAX_API_CONFIG[query_prov]['base_url']
        headers = get_optimized_headers(base_url)
        session = requests.Session()
        session.verify = False
        session.headers.update(headers)
        retry_count = 0
        logger.info(f"\n===== 开始查询 {query_prov} =====")

        while retry_count < max_retries_per_province:
            retry_count += 1
            ts = str(int(time.time() * 1000))
            try:
                # 获取验证码
                captcha_url = f"{base_url}/xxbg/api/zhsffw/sxsq/yzm/generate?djxh=&_={ts}"
                captcha_data = {"Width":100,"Height":32,"CodeCount":4,"Thickness":2,"SxzlCode":"GGCX_NSRZTCX"}
                cap_resp = session.post(captcha_url, json=captcha_data, timeout=8)
                cap_json = cap_resp.json()
                cap_id = cap_json.get("Response",{}).get("Data",{}).get("Result",{}).get("id")
                cap_img = cap_json.get("Response",{}).get("Data",{}).get("Result",{}).get("imageBase64Data") or cap_json.get("Response",{}).get("Data",{}).get("Result",{}).get("image")
                logger.info(f"{query_prov} 第{retry_count}次 | ID:{'✅' if cap_id else '❌'}")
                if not cap_id or not cap_img:
                    continue

                # 严格原生识别
                code = recognize_captcha(cap_img, query_prov)
                if not code:
                    continue

                # 识别成功，提交查询
                query_url = f"{base_url}/xxbg/api/zhsffw/ggcx/nsrztcx/queryNsrztcxList?djxh=&_={ts}"
                query_data = {"Nsrsbh":nsrsbh,"Nsrmc":"","Code":code,"Id":cap_id}
                q_resp = session.post(query_url, json=query_data, timeout=8)
                res_json = q_resp.json()

                if "Response" in res_json:
                    data = res_json.get("Response",{}).get("Data",{})
                    if data.get("Success"):
                        res_list = data.get("Result",[])
                        results.append(f"✅ {query_prov} 查询成功")
                        if res_list:
                            for item in res_list:
                                results.append(f"   纳税人识别号：{item.get('nsrsbh','')}")
                                results.append(f"   纳税人名称：{item.get('nsrmc','')}")
                                results.append(f"   主管税务机关：{item.get('swjgmc','')}")
                                results.append(f"   纳税人状态：{item.get('nsrztMc','')}")
                        else:
                            results.append("   查询结果为空（企业可能未税务登记）")
                        success = True
                        break
                    else:
                        err = data.get("Error",{}).get("message","未知错误")
                        if "验证码" in err:
                            logger.warning(f"{query_prov} 验证码错误，刷新重试")
                            continue
                        results.append(f"❌ {query_prov} 查询失败: {err}")
                        break
            except Exception as e:
                logger.error(f"{query_prov} 第{retry_count}次异常: {str(e)}")
                continue
        session.close()
        if success:
            break

    if success:
        results.append("="*50)
        results.append(f"⏱️ 总耗时：{round(time.time()-start_time,2)}秒")
        results.append("✅ 查询成功（原生4位验证码校验通过）")
    else:
        results.append("="*50)
        results.append("❌ 所有省份原生识别均未获取4位验证码，请稍后重试")
    results.append("="*50)
    cache_result(nsrsbh, results)
    return results

# -------------------------- 清税证明查询 --------------------------
def query_clearance(nsrsbh):
    results = []
    try:
        province = CreditCodeProvince.get_province_from_credit_code(nsrsbh)
    except:
        province = None
    CLEARANCE_URLS = {
        '北京市':'https://etax.beijing.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '天津市':'https://etax.tianjin.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '河北省':'https://etax.hebei.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '山西省':'https://etax.shanxi.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '内蒙古自治区':'https://etax.neimenggu.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '辽宁省':'https://etax.liaoning.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '吉林省':'https://etax.jilin.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '黑龙江省':'https://etax.heilongjiang.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '上海市':'https://etax.shanghai.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '江苏省':'https://etax.jiangsu.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '浙江省':'https://etax.zhejiang.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '安徽省':'https://etax.anhui.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '福建省':'https://etax.fujian.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '江西省':'https://etax.jiangxi.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '山东省':'https://etax.shandong.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '河南省':'https://etax.henan.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '湖北省':'https://etax.hubei.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '湖南省':'https://etax.hunan.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '广东省':'https://etax.guangdong.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '深圳市':'https://etax.shenzhen.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '广西壮族自治区':'https://etax.guangxi.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '海南省':'https://etax.hainan.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '重庆市':'https://etax.chongqing.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '四川省':'https://etax.sichuan.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '贵州省':'https://etax.guizhou.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '云南省':'https://etax.yunnan.chinatax.gov.cn/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '西藏自治区':'https://etax.xizang.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '陕西省':'https://etax.shaanxi.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '甘肃省':'https://etax.gansu.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '青海省':'https://etax.qinghai.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '宁夏回族自治区':'https://etax.ningxia.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '新疆维吾尔自治区':'https://etax.xinjiang.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs'
    }
    results.append(f"信用代码：{nsrsbh}")
    results.append(f"所属省份：{province or '未知'}")
    if province in CLEARANCE_URLS:
        results.append(f"🔗 [打开{province}清税证明页面]({CLEARANCE_URLS[province]})")
    elif province in UNAVAILABLE_PROVINCES:
        results.append("⚠️ 港澳台地区暂不支持清税证明查询")
    else:
        results.append("⚠️ 该地区清税证明查询暂未开通")
    results.append("="*50)
    return results

# -------------------------- 界面 --------------------------
def main():
    st.set_page_config(page_title="全国税务查询系统", page_icon="📋", layout="wide")
    st.title("全国税务查询系统（双模型原生4位识别版）")
    mode = st.radio("查询模式", ["纳税人状态查询（全国）", "清税证明查询（全国）"], horizontal=True)
    text = st.text_area("输入统一社会信用代码（每行一个，18位）", height=150)
    if st.button("开始查询", use_container_width=True):
        if not text.strip():
            st.error("请输入至少一个信用代码")
            return
        codes = [i.strip() for i in text.splitlines() if i.strip() and len(i.strip()) == 18]
        invalid_codes = [i.strip() for i in text.splitlines() if i.strip() and len(i.strip()) != 18]
        if invalid_codes:
            st.warning(f"格式错误（非18位）：{', '.join(invalid_codes)}")
        if not codes:
            st.error("无有效信用代码")
            return
        all_res = []
        with st.spinner(f"查询{len(codes)}个企业，双模型+全模板原生识别验证码..."):
            for c in codes:
                if mode == "纳税人状态查询（全国）":
                    all_res.extend(query_taxpayer_status(c))
                else:
                    all_res.extend(query_clearance(c))
        st.success("查询完成")
        st.markdown("<br>".join(all_res), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
