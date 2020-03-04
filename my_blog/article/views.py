from django.shortcuts import render, redirect
from .models import ArticlePost, ArticleColumn
import markdown
from .forms import ArticlePostForm
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator  # 分页模块
from django.db.models import Q
from comment.models import Comment
from comment.forms import CommentForm


def article_list(request):
    # 从 url 中提取查询参数
    search = request.GET.get('search')
    order = request.GET.get('order')
    column = request.GET.get('column')
    tag = request.GET.get('tag')

    # 初始化查询集
    article_list = ArticlePost.objects.all()

    # 搜索查询集
    if search:
        article_list = article_list.filter(
            Q(title__icontains=search) |
            Q(body__icontains=search)
        )
    else:
        search = ''

    # 栏目查询集
    if column is not None and column.isdigit():
        article_list = article_list.filter(column=column)

    # 标签查询集
    if tag and tag != 'None':
        article_list = article_list.filter(tags__name__in=[tag])

    # 查询集排序
    if order == 'total_views':
        article_list = article_list.order_by('-total_views')

    paginator = Paginator(article_list, 3)
    page = request.GET.get('page')
    articles = paginator.get_page(page)

    # 需要传递给模板（templates）的对象
    context = {
        'articles': articles,
        'order': order,
        'search': search,
        'column': column,
        'tag': tag,
    }

    return render(request, 'article/list.html', context)


# 文章详情
def article_detail(request, id):
    # 取出相应文章
    article = ArticlePost.objects.get(id=id)
    # 浏览量 +1
    article.total_views += 1
    article.save(update_fields=['total_views'])
    # 取出文章评论
    comments = Comment.objects.filter(article=id)
    # 引入评论表单
    comment_form = CommentForm()

    # 将markdown语法渲染成html样式
    md = markdown.Markdown(
        extensions=[
            'markdown.extensions.extra',
            'markdown.extensions.codehilite',
            'markdown.extensions.toc',
        ]
    )
    article.body = md.convert(article.body)
    # 需要传递给模板的对象
    context = {'article': article, 'toc': md.toc, 'comments': comments, 'comment_form': comment_form}
    # 载入模板，并返回context对象
    return render(request, 'article/detail.html', context)


# 写文章的视图
@login_required(login_url='/userprofile/login/')
def article_create(request):
    # 判断用户是否提交
    if request.method == "POST":
        # 将提交的数据赋值到表单实例中
        article_post_form = ArticlePostForm(request.POST, request.FILES)
        # 判断提交的数据是否满足模型的要求
        if article_post_form.is_valid():
            # 保存数据，但是暂时不提交数据库
            new_article = article_post_form.save(commit=False)
            # 指定数据库中 id=1 的用户为作者
            # 如果你进行过删除数据表的操作，可能会找不到id=1的用户
            # 此时请重新创建用户，并传入此用户的id
            # 指定当前登录的用户为作者
            new_article.author = User.objects.get(id=request.user.id)
            if request.POST['column'] != 'none':
                new_article.column = ArticleColumn.objects.get(id=request.POST['column'])
            # 将文章保存到数据库
            new_article.save()
            # 保存 tags 多对多的关系
            article_post_form.save_m2m()
            # 完成后返回到文章列表
            return redirect("article:article_list")
        # 如果数据不合法 返回错误信息
        else:
            return HttpResponse("表单内容有误，请重新填写。")
    else:
        # 创建表单实例
        article_post_form = ArticlePostForm()
        columns = ArticleColumn.objects.all()
        # 赋值上下文
        context = {'article_post_form': article_post_form, 'columns': columns}
        # 返回模板
        return render(request, 'article/create.html', context)


# 删除文章
@login_required(login_url='/userprofile/login/')
def article_safe_delete(request, id):
    article = ArticlePost.objects.get(id=id)
    # 过滤非作者的用户
    if request.user != article.author:
        return HttpResponse("抱歉，你无权修改这篇文章。")
    if request.method == "POST":
        # 根据id获取需要删除的文章
        article.delete()
        # 完成删除后返回文章列表
        return redirect("article:article_list")
    else:
        return HttpResponse("仅允许post请求")


# 更新文章
@login_required(login_url='/userprofile/login/')
def article_update(request, id):
    """
    更新文章的视图函数
    通过POST方法提交表单，更新title,body字段
    GET方法进入初试表单页面
    :param request:
    :param id: 文章的 id
    :return:
    """

    # 获取需要修改的具体文章对象
    article = ArticlePost.objects.get(id=id)
    # 过滤非作者的用户
    if request.user != article.author:
        return HttpResponse("抱歉，你无权修改这篇文章。")
    # 判断用户是否为 POST 提交表单数据
    if request.method == "POST":
        # 将提交的数据赋值到表单实例中
        article_post_form = ArticlePostForm(data=request.POST)
        # 判断提交的数据是否慢模型的具体要求
        if article_post_form.is_valid():
            # 保存新写入的 title body 数据并保存
            article.title = request.POST['title']
            article.body = request.POST['body']
            if request.POST['column'] != 'none':
                article.column = ArticleColumn.objects.get(id=request.POST['column'])
            else:
                article.column = None
            article.save()
            # 完成后返回到修改后的文章中，需要传入文章的 id 值
            return redirect("article:article_detail", id=id)
        # 如果数据不合法，需要返回错误信息
        else:
            return HttpResponse("表单内容有误，请重新填写。")
    # 如果用户 GET 请求获取数据
    else:
        # 创建表单实例
        article_post_form = ArticlePostForm()
        columns = ArticleColumn.objects.all()
        # 赋值上下文 ，将 article 文章对象也传递进去 以便提取旧的内容
        context = {'article': article, 'article_post_form': article_post_form, 'columns': columns}
        # 将响应返回到模板中
        return render(request, 'article/update.html', context)
