from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage, InvalidPage
from imacessor.settings import BASE_DIR
from math import ceil
import time
import json
import sqlite3
import base64
import os

# CONST VARIABLES
LIST_NUM = 5  # 操作历史分页显示：单页显示的记录条数

# 错误提示信息汇总
existUser = {'error': 'user exists'}  # 注册输入用户已存在
invalidParam = {'error': 'invalid parameters'}  # 参数为空或者非法
illegalAccess = {'error': 'no valid session'}  # 非法访问,eg. wrong session_id
loggedIn = {'error': 'has logged in'}  # 已处于登录状态
nonexistentUser = {'error': 'no such a user'}  # 用户名参数为空 or 用户不存在
typePOST = {'error': 'require POST'}  # 应为POST请求
wrongPw = {'error': 'password is wrong'}  # 密码不正确

# 各接口对应网页汇总
logon_page = '''<h1>SIGN IN</h1>
<form action="/logon" method="post">
Username:<input type="text" name="username" value="%s"/></br>
Password:<input type="password" name="password" value="%s"/></br>
<input type="submit" value="Submit"/>
</form>
'''
login_page = '''<h1>LOGIN</h1>
<form action="/login" method="post">
Username:<input type="text" name="username" value="%s"/></br>
Password:<input type="password" name="password" value="%s"/></br>
<input type="submit" value="Login"/>
</form>
'''

has_login_page = '''<form action="/haslogin" method="post">
    Welcome <label>%s</label>!</br>
    <select name="choice"> 
		<option value='Logout'>Log Out</option> 	
		<option value='Enter'>Enter Website</option> 
    </select>  
    <input type="submit" value="Mode"/>
</form>
'''

has_logout_page = '''<form action="/" method="get">
User "%s": Your account has been logged out.</br>
<input type="submit" value="Return to Main Menu"/>
</form>
'''

logon_success_page = '''<form action="/login" method="post">
User "%s": You have successfully registered. You can now use your account to login!</br>
<input type="submit" value="Go to Login"/>
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


# 请求处理函数
# Create your views here.


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
        return HttpResponse(logon_success_page % username)


@csrf_exempt
def login(request):  # 登录
    # 已处于登录状态
    cookie_id = request.COOKIES.get('session_id')
    if cookie_id:
        return HttpResponseRedirect('/')

    # 未登录
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
    else:
        # 无异常，登录并分配session_id
        new_id = create_session_id(username, password)  # 生成新的session_id
        login_response = HttpResponseRedirect('/classify')
        login_response.set_cookie('session_id', new_id)  # 不设置过期时间
    return login_response


@csrf_exempt
def logout(request):  # 注销
    # 异常处理
    cookie_id = request.COOKIES.get('session_id')
    if not cookie_id:  # 没有Cookies
        return HttpResponseRedirect('/')
    else:  # 有Cookies
        if verify_session_id(cookie_id):  # Cookies有效
            user_info = { 'user': 'nothing' }
            user_info['user'] = verify_session_id(cookie_id)
            logout_response = HttpResponse(has_logout_page % user_info['user'])
            logout_response.delete_cookie('session_id')
            return logout_response
        else:  # Cookies无效
            return HttpResponse(json.dumps(illegalAccess), content_type="application/json")


@csrf_exempt
def starting_interface(request):  # 起始界面
    BASE_DIR = os.path.dirname(os.path.dirname(__file__))
    print(BASE_DIR)
    print(type(BASE_DIR))
    # 未登录情形
    if request.method == 'POST':
        # print(request.POST['choice'])
        if request.POST['choice'] == 'Signup':
            return HttpResponseRedirect('/logon')
        elif request.POST['choice'] == 'Login':
            return HttpResponseRedirect('/login')

    cookie_id = request.COOKIES.get('session_id')
    if cookie_id:  # 已登录情形
        user = verify_session_id(cookie_id)
        return HttpResponse(has_login_page % user)

    return render_to_response('start.html')


@csrf_exempt
def has_login(request):  # 处理已登录界面
    if request.POST['choice'] == 'Logout':
        return HttpResponseRedirect('/logout')
    elif request.POST['choice'] == 'Enter':
        return HttpResponseRedirect('/classify')


@csrf_exempt
def scan_operation_history(request):  # 查看历史操作记录
    cookie_id = request.COOKIES.get('session_id')
    user_name = verify_session_id(cookie_id)
    if not user_name:  # 未登录，跳转至起始主界面
        return HttpResponseRedirect('/login')
    else:  # 已登录，获取当前用户名
        pass

    # 删除数据操作
    if request.method == 'POST':
        conn = sqlite3.connect('onlineDB.db')
        user_cursor = conn.cursor()

        for item in request.POST.getlist('delete'):
            index = int(item[1:-1])
            user_cursor.execute('select image_name from history where id=?', (index,))  # 删除图片
            filename = user_cursor.fetchall()
            if os.path.exists(BASE_DIR + '/static/images/history/' + filename[0][0]):
                os.remove(BASE_DIR + '/static/images/history/' + filename[0][0])
            user_cursor.execute('delete from history where id=?', (index,))  # 删除数据记录
        user_cursor.close()
        conn.commit()
        conn.close()
        return HttpResponseRedirect('/operation-history')

    # 数据库访问操作
    conn = sqlite3.connect('onlineDB.db')
    user_cursor = conn.cursor()
    if user_name != 'Admin':
        user_cursor.execute('select * from history where username=?', (user_name,))
    else:
        user_cursor.execute('select * from history')
    op_history = user_cursor.fetchall()
    user_cursor.close()
    conn.close()

    image_set = []
    final_history = []
    for record in op_history:
        image_set.append(record[1])
        final_record = list(record[0:-1])
        front_ten_time = int(record[-1][0:10])
        final_record.append(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(front_ten_time)) + '.' + record[-1][10:])
        final_history.append(final_record)

    # 将数据按照规定每页显示 5 条, 进行分割
    show_member_paginator = Paginator(final_history, LIST_NUM)

    if request.method == "GET":
        # Fetch value of 'page'.(Default = 1)
        page = request.GET.get('page')
        try:
            members = show_member_paginator.page(page)
        except PageNotAnInteger:
            # 如果请求的页数不是整数, 返回第一页。
            members = show_member_paginator.page(1)
        except InvalidPage:
            # 如果请求的页数不存在, 重定向页面
            return HttpResponseRedirect('/operation-history')
        except EmptyPage:
            # 如果请求的页数不在合法的页数范围内，返回结果的最后一页。
            members = show_member_paginator.page(show_member_paginator.num_pages)

    template_view = 'page.html'
    return render(request, template_view, {'members': members})
