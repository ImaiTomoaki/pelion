

import os
import numpy as np
import json
import datetime
import cv2
from azure.storage.blob import BlockBlobService
import base64
from flask import Flask, request, Response

app = Flask(__name__)

account_name = 'moribuildingml7196774142'
account_key = 'UYOFFAa2/E5q3PBK327lwTUZjqa7plyQ07Jv9TXzYOMU+wte88EU31mwoZ8baspDXTnwBY+UyvwgrK38opQC2Q=='
container_name = 'azureml-blobstore-54ca3e7c-77ca-4504-bdfc-5431acd78d10'

def convert_json(js):
    bef_b64 = js['image1']['base64']
    bef_name = js['image1']['url'].split("/")[-1]
    bef_image = base64.b64decode(bef_b64)
    bef_image = np.frombuffer(bef_image, dtype=np.uint8)
    bef_image = cv2.imdecode(bef_image, cv2.IMREAD_COLOR)
    aft_b64 = js['image2']['base64']
    aft_name = js['image2']['url'].split("/")[-1]
    aft_image = base64.b64decode(aft_b64)
    aft_image = np.frombuffer(aft_image, dtype=np.uint8)
    aft_image = cv2.imdecode(aft_image, cv2.IMREAD_COLOR)
    return bef_image, aft_image, bef_name, aft_name

def save_image(image, blob_name):
    with open(blob_name, 'wb') as f:
        f.write(image)
    blobService = BlockBlobService(
        account_name = account_name,
        account_key = account_key
        )
    blobService.create_blob_from_path(
        container_name,
        blob_name,
        blob_name
        )
    os.remove(blob_name)

def get_background_subtraction(image1, image2, th = 100):
    fgbg = cv2.createBackgroundSubtractorMOG2(1, th)
    fgmask = fgbg.apply(image1)
    fgmask = fgbg.apply(image2)
    return fgmask

def noise_filt(image, filt = 3):
    neiborhood = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], np.uint8)
    img_erode = cv2.erode(image, neiborhood, iterations=filt)
    img_dilate = cv2.dilate(img_erode, neiborhood, iterations=filt)
    img_dilate_2 = cv2.dilate(img_dilate, neiborhood, iterations=filt)
    img_erode_2 = cv2.erode(img_dilate_2, neiborhood, iterations=filt)
    image = img_erode_2
    return image

def create_rect_list(fgmask, ignore_size = 1000):
    # 輪郭抽出
    contours, hierarchy = cv2.findContours(fgmask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    rect_list = []
    for i in range(0, len(contours)):
        # 差分の面積がignore_size以下であれば無視
        if cv2.contourArea(contours[i]) < ignore_size:
            continue
        rect = contours[i]
        x, y, w, h = cv2.boundingRect(rect)
        rect_list.append([x, y, w, h])
    return rect_list

def create_json(rect_list, bef_name, aft_name):
    dt_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    location = []
    for rect in rect_list:
        loc_dict = {'top':rect[1], 'left':rect[0], 'bottom':rect[1]+rect[3], 'right':rect[0]+rect[2]}
        location.append(loc_dict)
    jsonData = {
        'id' : str(dt_now.strftime('%Y%m%d_%H%M%S')),
        'message' : str(len(rect_list)) + 'ヶ所の環境変化を検出しました。',
        'image1' : bef_name,
        'image2' : aft_name,
        'location' : location
        }
    return jsonData

@app.route('/check', methods=['GET', 'POST'])
def process_image():
    try:
        
        if request.method != "POST":
            return 'GET METHOD'
        
        else:
            # データの変換処理
            bef_image, aft_image, bef_name, aft_name = convert_json(request.json)
            
            # コンテナーにBLOBファイルを追加
            save_image(aft_image, aft_name)
        
            # 背景差分
            fgmask = get_background_subtraction(bef_image, aft_image, th = 100)
            
            # ノイズ除去（オープニング、クロージング）
            fgmask = noise_filt(fgmask, filt = 2)
        
            # 矩形領域の抽出
            rect_list = create_rect_list(fgmask, ignore_size = 1000)
            
            # jsonデータの作成
            jsonData = create_json(rect_list, bef_name, aft_name)
            
            # HTTPレスポンスを送信
            return Response(response=json.dumps(jsonData), status=200)
        
    except:
        return 'exception'
    
if __name__ == "__main__":
    app.run()
