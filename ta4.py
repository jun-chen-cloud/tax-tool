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
        results.append(f"信用代码: {nsrsbh}")
        results.append(f"⚠️ 原省份不可查询，尝试随机查询: {', '.join(random_provinces)}")
    
    if not query_provinces:
        return [f"信用代码: {nsrsbh}", "无法识别省份/无可查询地区", "=============================="]

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
                        res = [f"信用代码: {nsrsbh}", f"查询省份: {query_prov}"]
                        if res_list:
                            for item in res_list:
                                res.append(f"纳税人识别号: {item.get('nsrsbh', '未知')}")
                                res.append(f"纳税人名称: {item.get('nsrmc', '未知')}")
                                res.append(f"主管税务机关: {item.get('swjgmc', '未知')}")
                                res.append(f"纳税人状态: {item.get('nsrztMc', '未知')}")
                        else:
                            res.append("查询不到数据")
                        res.append("==============================")
                        cache_result(nsrsbh, res)
                        return res
                    else:
                        err_msg = data.get("Error", {}).get("message", "查询失败")
                        if "验证码" not in err_msg:
                            res = [f"信用代码: {nsrsbh}", f"查询省份: {query_prov}", err_msg, "=============================="]
                            cache_result(nsrsbh, res)
                            return res
            except:
                continue
    return [f"信用代码: {nsrsbh}", "所有查询省份均失败，重试次数耗尽", "=============================="]
