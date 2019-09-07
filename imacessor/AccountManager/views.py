from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from math import ceil
import http.cookies
import json
import sqlite3
import base64

# 错误提示信息汇总
existUser = {'error': 'user exists'}  # 注册输入用户已存在
invalidParam = {'error': 'invalid parameters'}  # 参数为空或者非法
illegalAccess = {'error': 'no valid session'}  # 非法访问,eg. wrong session_id
loggedIn = {'error': 'has logged in'}  # 已处于登录状态
nonexistentUser = {'error': 'no such a user'}  # 用户名参数为空 or 用户不存在
typePOST = {'error': 'require POST'}  # 应为POST请求
wrongPw = {'error': 'password is wrong'}  # 密码不正确

# 各接口对应网页汇总
logon_page = '''<form action="/logon" method="post">
Username:<input type="text" name="username" value="%s"/></br>
Password:<input type="password" name="password" value="%s"/></br>
<input type="submit" value="Submit"/>
</form>
'''
login_page = '''<form action="/login" method="post">
Username:<input type="text" name="username" value="%s"/></br>
Password:<input type="password" name="password" value="%s"/></br>
<input type="submit" value="Login"/>
</form>
'''


# 后台处理辅助函数
def judge_user_exist(user_name, pw):  # 判断注册输入用户是否已存在
    conn = sqlite3.connect('onlineDB.db')
    user_cursor = conn.cursor()

    user_cursor.execute('select * from user where username=?', (user_name,))
    user = user_cursor.fetchall()

    # 不存在时存储当前用户
    if not user:
        pw = base64.b64encode(pw.encode('ascii'))
        stored_pw = pw.decode('ascii')
        user_cursor.execute("insert into user (username, password) values ('%s','%s')" % (user_name, stored_pw))

    user_cursor.close()
    conn.commit()
    conn.close()
    if user:
        return True
    else:
        return False


def find_db_user(user_name, pw):  # 在数据库中寻找登录输入用户
    conn = sqlite3.connect('onlineDB.db')
    user_cursor = conn.cursor()

    user_cursor.execute('select * from user where username=?', (user_name,))
    user = user_cursor.fetchall()

    user_cursor.close()
    conn.commit()
    conn.close()

    if not user:  # 用户不存在
        return 0
    else:
        pw = base64.b64encode(pw.encode('ascii'))
        stored_pw = pw.decode('ascii')
        if user[0][1] != stored_pw:  # 密码不正确
            return 1
        else:  # 无异常
            return 2


def create_session_id(user_name, pw):  # 生成Cookies中的session_id
    user_name = base64.b64encode(user_name.encode('ascii'))
    encrp_id = user_name.decode('ascii')  # 加密用户名
    pw = base64.b64encode(pw.encode('ascii'))
    encrp_pw = pw.decode('ascii')  # 加密密码

    half_length = ceil(len(encrp_pw) / 2)
    str_hl = str(half_length)
    if len(str_hl) == 1:
        str_hl = '0' + str_hl

    session_id = str_hl + encrp_pw[0:half_length] + encrp_id
    return session_id


def verify_session_id(cookie):  # 校验Cookies中的session_id是否合法
    str_hl = cookie[0:2]
    half_length = 0
    if str_hl[0] == '0':
        half_length = int(str_hl[1])
    else:
        half_length = int(str_hl)

    cookie = cookie[2:]
    half_password = cookie[0:half_length]
    user_name = base64.b64decode(cookie[half_length:].encode('ascii')).decode('ascii')

    # 访问数据库
    conn = sqlite3.connect('onlineDB.db')
    user_cursor = conn.cursor()
    user_cursor.execute('select * from user where username=?', (user_name,))
    user = user_cursor.fetchall()
    user_cursor.close()
    conn.close()

    if not user:
        return False
    if user[0][1][0:half_length] == half_password:
        return user_name
    else:
        return False


# Create your views here.
def index(request):
    return HttpResponse('Hello!')


@csrf_exempt
def logon(request):  # 注册

    if 'username' in request.POST:
        username = request.POST['username']
        password = request.POST['password']
    else:
        username = ''
        password = ''
        return HttpResponse(logon_page % (username, password))

    # 异常处理
    if request.method == 'GET':
        return HttpResponse(json.dumps(typePOST), content_type="application/json")

    if not username or not password:
        return HttpResponse(json.dumps(invalidParam), content_type="application/json")
    elif judge_user_exist(username, password):
        return HttpResponse(json.dumps(existUser), content_type="application/json")
    else:  # 无异常
        user_info = {'user': username}
        return HttpResponse(json.dumps(user_info), content_type="application/json")


@csrf_exempt
def login(request):  # 登录
    if 'username' in request.POST:
        username = request.POST['username']
        password = request.POST['password']
    else:
        username = ''
        password = ''
        return HttpResponse(login_page % (username, password))

    # 异常处理
    if request.method == 'GET':
        return HttpResponse(json.dumps(typePOST), content_type="application/json")

    status = find_db_user(username, password)
    if status == 0:  # 用户不存在
        return HttpResponse(json.dumps(nonexistentUser), content_type="application/json")
    elif status == 1:  # 密码不正确
        return HttpResponse(json.dumps(wrongPw), content_type="application/json")
    elif status == 2:
        cookie_id = request.COOKIES.get('session_id')
        if cookie_id:  # 已处于登录状态
            if verify_session_id(cookie_id):  # *Cookies正常
                return HttpResponse(json.dumps(loggedIn), content_type="application/json")
            else:  # *Cookies内容异常
                return HttpResponse(json.dumps(illegalAccess), content_type="application/json")
        else:  # 无异常，登录并分配session_id
            new_id = create_session_id(username, password)  # 生成新的session_id
            user_info = {'user': username}
            login_response = HttpResponse(json.dumps(user_info))
            login_response.set_cookie('session_id', new_id)  # 不设置过期时间
        return login_response


@csrf_exempt
def logout(request):  # 注销
    # 异常处理
    if request.method == 'GET':
        return HttpResponse(json.dumps(typePOST), content_type="application/json")

    cookie_id = request.COOKIES.get('session_id')
    if not cookie_id:  # 没有Cookies
        return HttpResponse(json.dumps(illegalAccess), content_type="application/json")
    else:  # 有Cookies
        if verify_session_id(cookie_id):  # Cookies有效
            user_info = { 'user': 'nothing' }
            user_info['user'] = verify_session_id(cookie_id)
            logout_response = HttpResponse(json.dumps(user_info))
            logout_response.delete_cookie('session_id')
            return logout_response
        else:  # Cookies无效
            return HttpResponse(json.dumps(illegalAccess), content_type="application/json")

