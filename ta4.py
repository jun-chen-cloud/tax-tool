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

# 日志配置 - 输出到控制台+页面
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
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

# -------------------------- 核心工具函数 --------------------------
def get_optimized_headers(base_url):
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
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

def get_baidu_token():
    global BAIDU_TOKEN, BAIDU_TOKEN_EXPIRE
    if BAIDU_TOKEN and BAIDU_TOKEN_EXPIRE and datetime.now() < BAIDU_TOKEN_EXPIRE:
        logger.info("使用缓存百度Token")
        return BAIDU_TOKEN
    for _ in range(2):
        try:
            url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={BAIDU_API_KEY}&client_secret={BAIDU_SECRET_KEY}"
            resp = requests.get(url, timeout=6, verify=False)
            data = resp.json()
            BAIDU_TOKEN = data["access_token"]
            BAIDU_TOKEN_EXPIRE = datetime.now() + timedelta(hours=24)
            logger.info("百度Token获取成功")
            return BAIDU_TOKEN
        except Exception as e:
            logger.warning(f"Token获取重试失败: {e}")
            time.sleep(0.5)
    logger.error("百度Token获取彻底失败")
    return None

def recognize_captcha(captcha_image):
    # 【严格保留：必须4位纯字母数字，规则不动】
    token = get_baidu_token()
    if not token:
        logger.error("无百度Token，无法识别验证码")
        return None
    for retry in range(2):
        try:
            if captcha_image.startswith('data:image/'):
                base64_part = captcha_image.split(',')[1]
            else:
                base64_part = captcha_image
            import urllib.parse
            url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/webimage?access_token={token}"
            payload = f'image={urllib.parse.quote_plus(base64_part)}&detect_direction=false&single_line=true'
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            resp = requests.post(url, headers=headers, data=payload.encode("utf-8"), timeout=8, verify=False)
            result = resp.json()
            if 'error_code' in result:
                logger.warning(f"OCR识别错误码: {result['error_code']}, 重试{retry+1}")
                time.sleep(0.3)
                continue
            if 'words_result' in result and len(result['words_result']) > 0:
                raw_text = result['words_result'][0]['words']
                code = ''.join(filter(str.isalnum, raw_text))
                logger.info(f"OCR原始识别文本: {raw_text}, 过滤后: {code}")
                # 严格校验4位
                if len(code) == 4:
                    logger.info(f"✅ 验证码识别成功: {code}")
                    return code
                else:
                    logger.warning(f"❌ 验证码长度不符合，需4位，实际{len(code)}位")
                    return None
            logger.warning("OCR未识别到文字")
            return None
        except Exception as e:
            logger.warning(f"验证码识别异常重试{retry+1}: {e}")
            time.sleep(0.3)
    return None

def identify_province(nsrsbh):
    try:
        province = CreditCodeProvince.get_province_from_credit_code(nsrsbh)
        logger.info(f"信用代码{nsrsbh}识别省份: {province}")
        if not province:
            return None
        if province in PROVINCE_TAX_API_CONFIG:
            return province
        if province in ERROR_PROVINCES:
            logger.info(f"{province}属于不可查询省份")
            return None
        return None
    except Exception as e:
        logger.warning(f"省份识别异常: {e}")
        return None

def get_random_province():
    high_stable = ['广东省','深圳市','浙江省','江苏省','上海市','北京市','重庆市','湖北省']
    valid = [p for p in high_stable if p in PROVINCE_TAX_API_CONFIG.keys()]
    if valid:
        return random.choice(valid)
    valid_provinces = list(PROVINCE_TAX_API_CONFIG.keys())
    return random.choice(valid_provinces) if valid_provinces else None

def get_cached_result(nsrsbh):
    if nsrsbh in TAXPAYER_QUERY_CACHE:
        entry = TAXPAYER_QUERY_CACHE[nsrsbh]
        if time.time() - entry["timestamp"] < CACHE_EXPIRY_TIME:
            return entry["result"]
        del TAXPAYER_QUERY_CACHE[nsrsbh]
    return None

def cache_result(nsrsbh, result):
    TAXPAYER_QUERY_CACHE[nsrsbh] = {"result": result, "timestamp": time.time()}

# -------------------------- 税务状态查询（新增完整失败日志） --------------------------
def query_taxpayer_status(nsrsbh):
    cached = get_cached_result(nsrsbh)
    if cached:
        logger.info(f"{nsrsbh} 使用缓存结果")
        return cached
    results = []
    debug_log = []  # 页面展示的失败明细日志
    province = identify_province(nsrsbh)
    query_provinces = []
    start_time = time.time()
    
    if province:
        query_provinces.append(province)
    else:
        random_provinces = []
        for _ in range(4):
            rand_prov = get_random_province()
            if rand_prov and rand_prov not in random_provinces:
                random_provinces.append(rand_prov)
        query_provinces.extend(random_provinces)
        results.append(f"信用代码：{nsrsbh}")
        results.append(f"⚠️ 原省份不可查询，尝试随机查询：{', '.join(random_provinces)}")
        results.append("")
    
    if not query_provinces:
        results.append(f"信用代码：{nsrsbh}")
        results.append("无法识别省份/无可查询地区")
        results.append("="*50)
        cache_result(nsrsbh, results)
        return results

    max_retries_per_province = 4
    for query_prov in query_provinces:
        base_url = PROVINCE_TAX_API_CONFIG[query_prov]['base_url']
        headers = get_optimized_headers(base_url)
        retry_count = 0
        debug_log.append(f"\n【尝试省份：{query_prov}】")
        logger.info(f"===== 开始查询省份: {query_prov} =====")
        
        while retry_count < max_retries_per_province:
            retry_count += 1
            timestamp = str(int(time.time() * 1000))
            captcha_url = f"{base_url}/xxbg/api/zhsffw/sxsq/yzm/generate?djxh=&_={timestamp}"
            
            session = requests.Session()
            session.verify = False
            try:
                time.sleep(random.uniform(0.2, 0.6))
                logger.info(f"{query_prov} 第{retry_count}次重试，获取验证码")
                captcha_data = {"Width": 100, "Height": 32, "CodeCount": 4, "Thickness": 2, "SxzlCode": "GGCX_NSRZTCX"}
                captcha_resp = session.post(captcha_url, json=captcha_data, headers=headers, timeout=10)
                captcha_result = captcha_resp.json()
                captcha_id = None
                captcha_image = None
                if "Response" in captcha_result:
                    res_data = captcha_result.get("Response", {}).get("Data", {}).get("Result", {})
                    captcha_id = res_data.get("id")
                    captcha_image = res_data.get("imageBase64Data") or res_data.get("image")
                logger.info(f"{query_prov} 验证码ID: {captcha_id is not None}, 图片获取: {captcha_image is not None}")
                debug_log.append(f"  第{retry_count}次：验证码获取{'成功' if captcha_id else '失败'}")
                
                if not captcha_id or not captcha_image:
                    session.close()
                    continue
                
                captcha_code = recognize_captcha(captcha_image)
                debug_log.append(f"  验证码识别结果: {captcha_code if captcha_code else '识别失败(非4位纯字符)'}")
                if not captcha_code:
                    session.close()
                    continue
                
                time.sleep(random.uniform(0.2, 0.5))
                query_url = f"{base_url}/xxbg/api/zhsffw/ggcx/nsrztcx/queryNsrztcxList?djxh=&_={timestamp}"
                query_data = {"Nsrsbh": nsrsbh, "Nsrmc": "", "Code": captcha_code, "Id": captcha_id}
                query_resp = session.post(query_url, json=query_data, headers=headers, timeout=10)
                result = query_resp.json()
                session.close()
                
                logger.info(f"{query_prov} 接口返回: {result.get('Response',{}).get('Data',{})}")
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
                        cost_time = round(time.time() - start_time,2)
                        results.append("="*50)
                        results.append(f"查询耗时：{cost_time}秒")
                        results.append("="*50)
                        cache_result(nsrsbh, results)
                        return results
                    else:
                        err_msg = data.get("Error", {}).get("message", "查询失败")
                        debug_log.append(f"  接口报错: {err_msg}")
                        logger.warning(f"{query_prov} 接口业务报错: {err_msg}")
                        if "验证码" not in err_msg:
                            results.append(f"信用代码：{nsrsbh}")
                            results.append(f"查询省份：{query_prov}")
                            results.append(err_msg)
                            results.append("="*50)
                            cache_result(nsrsbh, results)
                            return results
            except requests.exceptions.Timeout:
                err = "接口超时"
                debug_log.append(f"  第{retry_count}次：{err}")
                logger.warning(f"{query_prov} {err}")
                session.close()
                continue
            except requests.exceptions.ConnectionError:
                err = "连接被拒绝/IP被风控"
                debug_log.append(f"  第{retry_count}次：{err}")
                logger.warning(f"{query_prov} {err}")
                session.close()
                continue
            except Exception as e:
                err = f"未知异常: {str(e)}"
                debug_log.append(f"  第{retry_count}次：{err}")
                logger.warning(f"{query_prov} {err}")
                session.close()
                continue
    
    # 所有省份全部失败，拼接失败日志到结果
    results.append(f"信用代码：{nsrsbh}")
    results.append("所有查询省份均失败，重试次数耗尽")
    results.append("\n【失败详细日志】")
    results.extend(debug_log)
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
    results.append("="*50)
    return results

# -------------------------- 网页主界面 --------------------------
def main():
    st.set_page_config(page_title="税务查询系统", page_icon="📋", layout="wide")
    st.title("税务查询系统")
    
    mode = st.radio("请选择查询模式", ["查税务状态", "查清税证明"], horizontal=True)
    input_text = st.text_area("请输入18位纳税人识别号（支持批量，每行一个）", height=100)
    
    if st.button("开始查询", use_container_width=True):
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
                        all_results.append(f"{code} → 格式错误（必须18位）")
                        all_results.append("="*50)
            else:
                for code in nsrsbh_list:
                    if len(code) == 18:
                        all_results.extend(query_clearance(code))
                    else:
                        all_results.append(f"{code} → 格式错误（必须18位）")
                        all_results.append("="*50)
        
        st.success("查询完成！")
        st.markdown("<br>".join(all_results), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
