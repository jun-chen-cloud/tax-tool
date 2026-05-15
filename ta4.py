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
from datetime import datetime
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

# 税务接口配置【保留8443端口，完全不变】
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

# 修复Base64解码函数
def safe_base64_decode(img_base64):
    try:
        if "," in img_base64:
            img_base64 = img_base64.split(",")[1]
        img_base64 = img_base64.strip().replace(" ", "").replace("\n", "")
        missing_padding = len(img_base64) % 4
        if missing_padding:
            img_base64 += "=" * (4 - missing_padding)
        return base64.b64decode(img_base64)
    except:
        return None

# -------------------------- 税务状态查询 --------------------------
def query_taxpayer_status_manual(nsrsbh, captcha_id, captcha_code, province, session):
    cached = get_cached_result(nsrsbh)
    if cached:
        return cached
    results = []
    start_time = time.time()
    base_url = PROVINCE_TAX_API_CONFIG[province]['base_url']
    headers = get_optimized_headers(base_url)

    try:
        timestamp = str(int(time.time() * 1000))
        query_url = f"{base_url}/xxbg/api/zhsffw/ggcx/nsrztcx/queryNsrztcxList?djxh=&_={timestamp}"
        query_data = {"Nsrsbh": nsrsbh, "Nsrmc": "", "Code": captcha_code, "Id": captcha_id}
        query_resp = session.post(query_url, json=query_data, headers=headers, timeout=10)
        result = query_resp.json()

        if "Response" in result:
            data = result.get("Response", {}).get("Data", {})
            if data.get("Success"):
                res_list = data.get("Result", [])
                results.append(f"信用代码：{nsrsbh}")
                if res_list:
                    for item in res_list:
                        results.append(f"纳税人识别号：{item.get('nsrsbh', '未知')}")
                        results.append(f"纳税人名称：{item.get('nsrmc', '未知')}")
                        results.append(f"主管税务机关：{item.get('swjgmc', '未知')}")
                        results.append(f"纳税人状态：{item.get('nsrztMc', '未知')}")
                else:
                    results.append("查询不到数据")
                cost_time = round(time.time() - start_time, 2)
                results.append("=" * 50)
                results.append(f"查询耗时：{cost_time}秒")
                results.append("=" * 50)
                cache_result(nsrsbh, results)
                return results
            else:
                err_msg = data.get("Error", {}).get("message", "查询失败")
                results.append(f"信用代码：{nsrsbh}")
                results.append(f"查询省份：{province}")
                results.append(err_msg)
                results.append("=" * 50)
                cache_result(nsrsbh, results)
                return results
    except Exception as e:
        results.append(f"信用代码：{nsrsbh}")
        results.append(f"查询异常：{str(e)}")
        results.append("=" * 50)
        return results

# -------------------------- 清税证明查询 --------------------------
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
        results.append(f"信用代码：{nsrsbh}")
        results.append(f"所属省份：{province}")
        results.append(f"🔗 [点击直接打开清税证明页面]({url})")
    else:
        results.append(f"信用代码：{nsrsbh}")
        results.append(f"所属省份：{province or '未知'}")
        results.append("该地区暂不支持在线清税证明查询")
    results.append("=" * 50)
    return results

# -------------------------- 主界面（修复：点一次查询生效） --------------------------
def main():
    st.set_page_config(page_title="税务查询系统", page_icon="📋", layout="wide")
    st.title("税务查询系统")
    st.divider()

    # 初始化会话
    if "captcha_id" not in st.session_state:
        st.session_state.captcha_id = None
    if "captcha_img" not in st.session_state:
        st.session_state.captcha_img = None
    if "tax_session" not in st.session_state:
        st.session_state.tax_session = None
    if "query_province" not in st.session_state:
        st.session_state.query_province = None

    # 查询模式
    mode = st.radio("请选择查询模式", ["查税务状态", "查清税证明"], horizontal=True)
    input_text = st.text_area(
        label="纳税人识别号输入框",
        placeholder="请输入18位纳税人识别号（支持批量，每行一个）",
        height=100,
        label_visibility="hidden"
    )

    st.divider()

    # 验证码模块
    st.subheader("验证码操作")
    col1, col2 = st.columns([1, 1])
    with col1:
        get_captcha_btn = st.button("🔄 获取验证码", type="secondary")

    if get_captcha_btn and mode == "查税务状态":
        nsrsbh_list = [i.strip() for i in input_text.split("\n") if i.strip() and len(i.strip()) == 18]
        if not nsrsbh_list:
            st.error("❌ 请先输入有效的18位信用代码！")
        else:
            first_code = nsrsbh_list[0]
            target_province = identify_province(first_code) or get_random_province()

            try:
                base_url = PROVINCE_TAX_API_CONFIG[target_province]['base_url']
                if base_url not in SESSION_POOL:
                    sess = requests.Session()
                    sess.verify = False
                    SESSION_POOL[base_url] = sess
                session = SESSION_POOL[base_url]
                headers = get_optimized_headers(base_url)
                timestamp = str(int(time.time() * 1000))

                captcha_url = f"{base_url}/xxbg/api/zhsffw/sxsq/yzm/generate?djxh=&_={timestamp}"
                captcha_data = {"Width": 100, "Height": 32, "CodeCount": 4, "Thickness": 2, "SxzlCode": "GGCX_NSRZTCX"}
                captcha_resp = session.post(captcha_url, json=captcha_data, headers=headers, timeout=10)
                captcha_result = captcha_resp.json()

                if "Response" in captcha_result:
                    res_data = captcha_result.get("Response", {}).get("Data", {}).get("Result", {})
                    st.session_state.captcha_id = res_data.get("id")
                    img_base64 = res_data.get("imageBase64Data") or res_data.get("image")

                    if img_base64:
                        img_bytes = safe_base64_decode(img_base64)
                        if img_bytes:
                            st.session_state.captcha_img = img_bytes
                            st.session_state.tax_session = session
                            st.session_state.query_province = target_province
                            st.success(f"✅ 验证码获取成功（省份：{target_province}）")
            except Exception:
                pass

    # 🔥 核心修复：给验证码输入框加 key，实时同步状态，解决点两次问题
    user_captcha = ""
    if st.session_state.captcha_img and mode == "查税务状态":
        st.image(st.session_state.captcha_img, caption="请输入4位验证码", width=120)
        # 加 key="captcha_input" 强制实时保存输入值
        user_captcha = st.text_input("验证码", max_chars=4, label_visibility="hidden", key="captcha_input")
    elif mode == "查税务状态":
        st.info("👆 请先输入信用代码，再点击【获取验证码】")

    st.divider()

    # 开始查询（点一次就生效）
    if st.button("🚀 开始查询", use_container_width=True, type="primary"):
        if not input_text.strip():
            st.error("请输入纳税人识别号！")
            return

        # 🔥 核心修复：直接读取 session_state 实时值，不依赖变量
        user_captcha_real = st.session_state.get("captcha_input", "")
        nsrsbh_list = [i.strip() for i in input_text.split("\n") if i.strip()]
        all_results = []

        with st.spinner("查询中，请稍候..."):
            if mode == "查税务状态":
                if not all([st.session_state.captcha_id, user_captcha_real, len(user_captcha_real)==4, st.session_state.tax_session]):
                    st.error("❌ 请先获取并输入完整4位验证码！")
                    return

                for code in nsrsbh_list:
                    if len(code) == 18:
                        res = query_taxpayer_status_manual(
                            code,
                            st.session_state.captcha_id,
                            user_captcha_real,
                            st.session_state.query_province,
                            st.session_state.tax_session
                        )
                        all_results.extend(res)
                    else:
                        all_results.append(f"{code} → 格式错误（必须18位）")
                        all_results.append("=" * 50)
            else:
                for code in nsrsbh_list:
                    if len(code) == 18:
                        all_results.extend(query_clearance(code))
                    else:
                        all_results.append(f"{code} → 格式错误（必须18位）")
                        all_results.append("=" * 50)

        st.success("查询完成！")
        st.markdown("<br>".join(all_results), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
