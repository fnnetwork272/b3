

#RazorPay Charge 1$ Code And All Captured By @diwazz 


import requests

headers = {
    'Accept': '*/*',
    'Accept-Language': 'en-IN',
    'Connection': 'keep-alive',
    'Content-type': 'application/x-www-form-urlencoded',
    'Referer': 'https://api.razorpay.com/v1/checkout/public?traffic_env=production&build=ef9764309f65a1e8295cdadd332e1da6b3c0adbc&build_v1=cb2fc10e95cbac52b796c4f30abcfd48da438eef&checkout_v2=1&new_session=1&rzp_device_id=1.43d6daced12b197df96fe752f0d504569d483c35.1764923278911.61815454&unified_session_id=RnrdHfdyAgXHoY&session_token=4240A937FCD1249169B399AFA2BA971DBB99A6E11A22EBE67D2140758AC0135003EC71458E2891B441F23843AD46E1C4069522FDF0B03DB495D71FA2091A3AA14B0B6D9961695475E50B1335D3AD042EA1A60132230DA3A9422DDD5CBB1461E4F774EB5B9028DC81',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36',
    'sec-ch-ua': '"Chromium";v="127", "Not)A;Brand";v="99", "Microsoft Edge Simulate";v="127", "Lemur";v="127"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'x-session-token': '4240A937FCD1249169B399AFA2BA971DBB99A6E11A22EBE67D2140758AC0135003EC71458E2891B441F23843AD46E1C4069522FDF0B03DB495D71FA2091A3AA14B0B6D9961695475E50B1335D3AD042EA1A60132230DA3A9422DDD5CBB1461E4F774EB5B9028DC81',
}

params = {
    'key_id': 'rzp_live_RjYQK2vibEihg9',
    'session_token': '4240A937FCD1249169B399AFA2BA971DBB99A6E11A22EBE67D2140758AC0135003EC71458E2891B441F23843AD46E1C4069522FDF0B03DB495D71FA2091A3AA14B0B6D9961695475E50B1335D3AD042EA1A60132230DA3A9422DDD5CBB1461E4F774EB5B9028DC81',
    'keyless_header': 'api_v1:TyDZd53Wsad4qkUjkwQC3f6CBdTmzv23wK6qSlYuISSnuVpZ8X4d1Ff0K1fCacr4tBMExDlZS7jVvlJvEVYBXpAb4yaAFw==',
}

data = {
    'notes[comment]': '',
    'payment_link_id': 'pl_IdI5q8vLO8tAhg',
    'key_id': 'rzp_live_RjYQK2vibEihg9',
    'contact': '+919334462399',
    'email': 'khatrieex@gmail.com',
    'currency': 'INR',
    '_[checkout_id]': 'RnsHjjL48sV6ih',
    '_[device.id]': '1.43d6daced12b197df96fe752f0d504569d483c35.1764923279441.41032756',
    '_[env]': '',
    '_[library]': 'checkoutjs',
    '_[library_src]': 'no-src',
    '_[current_script_src]': 'no-src',
    '_[is_magic_script]': 'false',
    '_[platform]': 'browser',
    '_[referer]': 'https://razorpay.me/@ukinternational',
    '_[shield][fhash]': 'cc54eb693a9f90a545b601e98499b4c2c3b31dff',
    '_[shield][tz]': '345',
    '_[device_id]': '1.43d6daced12b197df96fe752f0d504569d483c35.1764923279441.41032756',
    '_[build]': '18372560617',
    '_[request_index]': '0',
    'amount': '100',
    'order_id': 'order_RnsHisNBaPJnPp',
    'device_fingerprint[fingerprint_payload]': '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',
    'user_risk_providers_token': 'W3sibmFtZSI6ImZpbmdlcnByaW50IiwibWV0YWRhdGEiOnsicmVxdWVzdF9pZCI6IjE3NjAzNDgwMjk1NDkuQlA1SDlUIn19XQ==',
    'method': 'card',
    'card[number]': '4266841816889552',
    'card[cvv]': '168',
    'card[name]': 'diwass',
    'card[expiry_month]': '03',
    'card[expiry_year]': '30',
    'save': '0',
    'billing_address[country]': 'IN',
    'billing_address[postal_code]': '19001',
    'billing_address[city]': 'Dhelhi',
    'billing_address[state]': 'Delhi',
    'billing_address[line1]': 'Ghar Ke Baaju ',
    'billing_address[line2]': 'Ka Bhaiya ',
    'currency_request_id': 'RSuRLEShxk59iJ',
    'dcc_currency': 'INR',
}

response = requests.post(
    'https://api.razorpay.com/v1/standard_checkout/payments/create/ajax',
    params=params,
    headers=headers,
    data=data,
)
print("wait...... processsinggvvvv")
print('Created  Payment Id ')
print('Payment  Id FOUND ')
print('Owner @diwazz ')
print('Now Final Response')
print(response.text)
payment_id = {"payment_id"}
