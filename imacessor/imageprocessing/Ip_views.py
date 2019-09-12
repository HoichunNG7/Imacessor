from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseRedirect
from .form import UploadImageForm
from .models import Image
from AccountManager.views import verify_session_id
import sqlite3
import os
import sys
import time
import tensorflow as tf


def get_status_timestamp():  # 获取当前时间戳
    now = time.time()
    millis = int(round(now * 1000))
    return millis


@csrf_exempt
def index(request):  # Upload images 上传图片
    cookie_id = request.COOKIES.get('session_id')
    user_name = verify_session_id(cookie_id)
    if not user_name:  # 未登录，跳转至起始主界面
        return HttpResponseRedirect('/login')
    else:  # 已登录，获取当前用户名
        pass

    if request.method == 'POST':  # “有内容”
        form = UploadImageForm(request.POST, request.FILES)
        if form.is_valid():
            picture = Image(photo=request.FILES['image'])
            picture.save()

            label = imageclassify(picture)
            time_stamp = get_status_timestamp()  # 获取当前时间戳

            # 数据库操作
            conn = sqlite3.connect('onlineDB.db')
            user_cursor = conn.cursor()
            user_cursor.execute("insert into history (image_name, username, image_class, timestamp) values ('%s','%s','%s','%s')" % (picture.photo.name, user_name, label[0][0], str(time_stamp)))
            user_cursor.close()
            conn.commit()
            conn.close()

            return render(request, 'show.html', {'picture': picture, 'label': label[0][0]})

    else:  # “无内容”
        form = UploadImageForm()

        return render(request, 'index.html', {'form': form})


@csrf_exempt
def imageclassify(picture):  # Classify images 进行图片识别与分类
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

    # image_path = picture

    # Read in the image_data
    image_data = tf.gfile.FastGFile(picture.photo.path, 'rb').read()

    # Loads label file, strips off carriage return
    label_lines = [line.rstrip() for line in tf.gfile.GFile("imageprocessing/retrained_labels.txt")]

    # Unpersists graph from file
    with tf.gfile.FastGFile("imageprocessing/retrained_graph.pb", 'rb') as f:
        graph_def = tf.GraphDef()
        graph_def.ParseFromString(f.read())
        tf.import_graph_def(graph_def, name='')

    with tf.Session() as sess:
        # Feed the image_data as input to the graph and get first prediction
        softmax_tensor = sess.graph.get_tensor_by_name('final_result:0')

        predictions = sess.run(softmax_tensor, {'DecodeJpeg/contents:0': image_data})

        # Sort to show labels of first prediction in order of confidence
        top_k = predictions[0].argsort()[-len(predictions[0]):][::-1]

        label = []
        i = 1
        for node_id in top_k:
            human_string = label_lines[node_id]
            score = predictions[0][node_id]
            # print('%s (score = %.5f)' % (human_string, score))
            a = (human_string, score)
            if i < 2:
                label.append(a)
                i += 1
            else:
                break
        return label

