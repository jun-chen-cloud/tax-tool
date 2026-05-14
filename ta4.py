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
warnings.filterwarnings("ignore")

# 关闭SSL警告
requests.packages.urllib3.disable_warnings()

os.environ.update({
    "PYTHONIOENCODING": "utf-8",
    "LC_ALL": "zh_CN.UTF-8",
    "LANG": "zh_CN.UTF-8"
})

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 百度OCR配置
BAIDU_API_KEY = "oML5Ne6i08WQn5nTgHb7atrq"
BAIDU_SECRET_KEY = "Y7BMTosC2QYkjoV9NZVZxZhmAFWaxb1E"
BAIDU_TOKEN = None
BAIDU_TOKEN_EXPIRE = None

# -------------------------- 省份映射 --------------------------
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

# 税务接口配置
PROVINCE_TAX_API_CONFIG = {
    '北京市': {'base_url': 'https://etax.beijing.chinatax.gov.cn:8443'},
    '天津市': {'base_url': 'https://etax.tianjin.chinatax.gov.cn:8443'},
    '河北省': {'base_url': 'https://etax.hebei.chinatax.gov.cn:8443'},
    '上海市': {'base_url': 'https://etax.shanghai.chinatax.gov.cn:8443'},
    '江苏省': {'base_url': 'https://etax.jiangsu.chinatax.gov.cn:8443'},
    '浙江省': {'base_url': 'https://etax.zhejiang.chinatax.gov.cn:8443'},
    '安徽省': {'base_url': 'https://etax.anhui.chinatax.gov.cn:8443'},
    '福建省': {'base_url': 'https://etax.fujian.chinatax.gov.cn:8443'},
    '广东省': {'base_url': 'https://etax.guangdong.chinatax.gov.cn:8443'},
    '深圳市': {'base_url': 'https://etax.guangdong.chinatax.gov.cn:8443'},
    '湖北省': {'base_url': 'https://etax.hubei.chinatax.gov.cn:8443'},
    '重庆市': {'base_url': 'https://etax.chongqing.chinatax.gov.cn:8443'},
    '贵州省': {'base_url': 'https://etax.guizhou.chinatax.gov.cn:8443'},
    '云南省': {'base_url': 'https://etax.yunnan.chinatax.gov.cn'},
    '甘肃省': {'base_url': 'https://etax.gansu.chinatax.gov.cn:8443'},
    '青海省': {'base_url': 'https://etax.qinghai.chinatax.gov.cn:8443'},
    '宁夏回族自治区': {'base_url': 'https://etax.ningxia.chinatax.gov.cn:8443'}
}

ERROR_PROVINCES = {
    '山东省', '湖南省', '吉林省', '新疆维吾尔自治区', '山西省', 
    '西藏自治区', '四川省', '陕西省', '内蒙古自治区', '辽宁省',
    '黑龙江省', '广西壮族自治区', '海南省', '河南省', '江西省'
}

# 缓存配置
TAXPAYER_QUERY_CACHE = {}
CACHE_EXPIRY_TIME = 3600
SESSION_POOL = {}

# -------------------------- 核心工具函数 --------------------------
def get_optimized_headers(base_url):
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Origin": base_url,
        "Referer": f"{base_url}/xxbg/view/zhsffw/",
        "requestid": str(int(time.time() * 1000)),
        "x-b3-traceid": str(uuid.uuid4()).replace("-", "")
    }

def get_baidu_token():
    global BAIDU_TOKEN, BAIDU_TOKEN_EXPIRE
    if BAIDU_TOKEN and BAIDU_TOKEN_EXPIRE and datetime.now() < BAIDU_TOKEN_EXPIRE:
        return BAIDU_TOKEN
    try:
        url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={BAIDU_API_KEY}&client_secret={BAIDU_SECRET_KEY}"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        BAIDU_TOKEN = data["access_token"]
        BAIDU_TOKEN_EXPIRE = datetime.now() + timedelta(hours=24)
        return BAIDU_TOKEN
    except Exception as e:
        logger.error(f"Token获取失败: {e}")
        return None

def recognize_captcha(captcha_image):
    token = get_baidu_token()
    if not token:
        return None
    try:
        if captcha_image.startswith('data:image/'):
            base64_part = captcha_image.split(',')[1]
        else:
            base64_part = captcha_image
        import urllib.parse
        url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/webimage?access_token={token}"
        payload = f'image={urllib.parse.quote_plus(base64_part)}&detect_direction=false'
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        resp = requests.post(url, headers=headers, data=payload.encode("utf-8"), timeout=5)
        result = resp.json()
        if 'error_code' in result:
            return None
        if 'words_result' in result and len(result['words_result']) > 0:
            code = ''.join(filter(str.isalnum, result['words_result'][0]['words']))
            return code if len(code) == 4 else None
        return None
    except Exception:
        return None

def identify_province(nsrsbh):
    try:
        province = CreditCodeProvince.get_province_from_credit_code(nsrsbh)
        if not province:
            return None
        if province in PROVINCE_TAX_API_CONFIG:
            return province
        if province in ERROR_PROVINCES:
            return None
        return None
    except:
        return None

def get_random_province():
    valid_provinces = list(PROVINCE_TAX_API_CONFIG.keys())
    if not valid_provinces:
        return None
    return random.choice(valid_provinces)

def get_cached_result(nsrsbh):
    if nsrsbh in TAXPAYER_QUERY_CACHE:
        entry = TAXPAYER_QUERY_CACHE[nsrsbh]
        if time.time() - entry["timestamp"] < CACHE_EXPIRY_TIME:
            return entry["result"]
        del TAXPAYER_QUERY_CACHE[nsrsbh]
    return None

def cache_result(nsrsbh, result):
    TAXPAYER_QUERY_CACHE[nsrsbh] = {"result": result, "timestamp": time.time()}

# -------------------------- 税务状态查询（排版修复版） --------------------------
def query_taxpayer_status(nsrsbh):
    cached = get_cached_result(nsrsbh)
    if cached:
        return cached
    results = []
    province = identify_province(nsrsbh)
    query_provinces = []
    if province:
        query_provinces.append(province)
    else:
        random_provinces = []
        for _ in range(3):
            rand_prov = get_random_province()
            if rand_prov and rand_prov not in random_provinces:
                random_provinces.append(rand_prov)
        query_provinces.extend(random_provinces)
        results.append(f"📋 信用代码: {nsrsbh}")
        results.append(f"⚠️ 原省份不可查询，尝试随机查询: {', '.join(random_provinces)}")
    
    if not query_provinces:
        results.append(f"📋 信用代码: {nsrsbh}")
        results.append("❌ 无法识别省份/无可查询地区")
        results.append("---")
        return results

    max_retries_per_province = 3
    for query_prov in query_provinces:
        base_url = PROVINCE_TAX_API_CONFIG[query_prov]['base_url']
        if base_url not in SESSION_POOL:
            sess = requests.Session()
            sess.verify = False
            SESSION_POOL[base_url] = sess
        session = SESSION_POOL[base_url]
        headers = get_optimized_headers(base_url)
        retry_count = 0
        
        while retry_count < max_retries_per_province:
            retry_count += 1
            timestamp = str(int(time.time() * 1000))
            captcha_url = f"{base_url}/xxbg/api/zhsffw/sxsq/yzm/generate?djxh=&_={timestamp}"
            try:
                captcha_data = {"Width": 100, "Height": 32, "CodeCount": 4, "Thickness": 2, "SxzlCode": "GGCX_NSRZTCX"}
                captcha_resp = session.post(captcha_url, json=captcha_data, headers=headers, timeout=8)
                captcha_result = captcha_resp.json()
                captcha_id = None
                captcha_image = None
                if "Response" in captcha_result:
                    res_data = captcha_result.get("Response", {}).get("Data", {}).get("Result", {})
                    captcha_id = res_data.get("id")
                    captcha_image = res_data.get("imageBase64Data") or res_data.get("image")
                if not captcha_id or not captcha_image:
                    continue
                captcha_code = recognize_captcha(captcha_image)
                if not captcha_code:
                    continue
                query_url = f"{base_url}/xxbg/api/zhsffw/ggcx/nsrztcx/queryNsrztcxList?djxh=&_={timestamp}"
                query_data = {"Nsrsbh": nsrsbh, "Nsrmc": "", "Code": captcha_code, "Id": captcha_id}
                query_resp = session.post(query_url, json=query_data, headers=headers, timeout=8)
                result = query_resp.json()
                if "Response" in result:
                    data = result.get("Response", {}).get("Data", {})
                    if data.get("Success"):
                        res_list = data.get("Result", [])
                        results.append(f"📋 信用代码: {nsrsbh}")
                        results.append(f"📍 查询省份: {query_prov}")
                        if res_list:
                            for item in res_list:
                                results.append(f"🆔 纳税人识别号: {item.get('nsrsbh', '未知')}")
                                results.append(f"🏢 纳税人名称: {item.get('nsrmc', '未知')}")
                                results.append(f"🏛️ 主管税务机关: {item.get('swjgmc', '未知')}")
                                status = item.get('nsrztMc', '未知')
                                if "正常" in status:
                                    results.append(f"✅ 纳税人状态: {status}")
                                elif "注销" in status or "非正常" in status:
                                    results.append(f"❌ 纳税人状态: {status}")
                                else:
                                    results.append(f"ℹ️ 纳税人状态: {status}")
                                results.append("---")
                        else:
                            results.append("⚠️ 查询不到数据")
                            results.append("---")
                        cache_result(nsrsbh, results)
                        return results
                    else:
                        err_msg = data.get("Error", {}).get("message", "查询失败")
                        if "验证码" not in err_msg:
                            results.append(f"📋 信用代码: {nsrsbh}")
                            results.append(f"📍 查询省份: {query_prov}")
                            results.append(f"❌ {err_msg}")
                            results.append("---")
                            cache_result(nsrsbh, results)
                            return results
            except:
                continue
    
    results.append(f"📋 信用代码: {nsrsbh}")
    results.append("❌ 所有查询省份均失败，重试次数耗尽")
    results.append("---")
    cache_result(nsrsbh, results)
    return results

# -------------------------- 清税证明查询（可点击链接版） --------------------------
def query_clearance(nsrsbh):
    results = []
    try:
        province = CreditCodeProvince.get_province_from_credit_code(nsrsbh)
    except:
        province = None
    CLEARANCE_URLS = {
        '北京市': 'https://etax.beijing.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '天津市': 'https://etax.tianjin.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '河北省': 'https://etax.hebei.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '上海市': 'https://etax.shanghai.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '江苏省': 'https://etax.jiangsu.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '浙江省': 'https://etax.zhejiang.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '安徽省': 'https://etax.anhui.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '福建省': 'https://etax.fujian.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '广东省': 'https://etax.guangdong.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '深圳市': 'https://etax.shenzhen.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '湖北省': 'https://etax.hubei.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '重庆市': 'https://etax.chongqing.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '贵州省': 'https://etax.guizhou.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '云南省': 'https://etax.yunnan.chinatax.gov.cn/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '甘肃省': 'https://etax.gansu.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '青海省': 'https://etax.qinghai.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs',
        '宁夏回族自治区': 'https://etax.ningxia.chinatax.gov.cn:8443/xxbg/view/ztxxbg/qssbswzxblwkyqs'
    }
    if province in CLEARANCE_URLS:
        url = CLEARANCE_URLS[province]
        results.append(f"**📋 信用代码**: {nsrsbh}")
        results.append(f"**📍 所属省份**: {province}")
        results.append(f"🔗 [点击直接打开清税证明页面]({url})")
    else:
        results.append(f"**📋 信用代码**: {nsrsbh}")
        results.append(f"**📍 所属省份**: {province or '未知'}")
        results.append("❌ 该地区暂不支持在线清税证明查询")
    results.append("---")
    return results

# -------------------------- Streamlit 网页主界面 --------------------------
def main():
    st.set_page_config(page_title="税务查询系统", page_icon="📋", layout="wide")
    st.title("📋 税务查询系统")
    
    # 查询模式选择
    mode = st.radio("请选择查询模式", ["查税务状态", "查清税证明"], horizontal=True)
    # 输入框
    input_text = st.text_area("请输入18位纳税人识别号（支持批量，每行一个）", height=100)
    # 查询按钮
    if st.button("🚀 开始查询", use_container_width=True):
        if not input_text.strip():
            st.error("请输入纳税人识别号！")
            return
        
        nsrsbh_list = [i.strip() for i in input_text.split("\n") if i.strip()]
        all_results = []
        
        with st.spinner("查询中，请稍候..."):
            if mode == "查税务状态":
                for code in nsrsbh_list:
                    if len(code) == 18:
                        all_results.extend(query_taxpayer_status(code))
                    else:
                        all_results.append(f"❌ {code} → 格式错误（必须18位）")
                        all_results.append("---")
            else:
                for code in nsrsbh_list:
                    if len(code) == 18:
                        all_results.extend(query_clearance(code))
                    else:
                        all_results.append(f"❌ {code} → 格式错误（必须18位）")
                        all_results.append("---")
        
        # 展示结果（排版修复+支持链接）
        st.success("查询完成！")
        st.markdown("\n\n".join(all_results), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
