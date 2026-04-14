from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AppSettingForm, CategoryForm, ExpenseEditForm
from .models import AppSetting, Category, Expense

from django.http import HttpResponse
from django.templatetags.static import static

from django.shortcuts import render, redirect
from .forms import SignUpForm


#フラッシュメッセージ(通知)　extra_tags="created"→cssで色変えるため
def flash_created(request, message):
    messages.success(request, message, extra_tags="created")


def flash_updated(request, message):
    messages.info(request, message, extra_tags="updated")


def flash_deleted(request, message):
    messages.error(request, message, extra_tags="deleted")

#アプリの設定を必ず1件取得する
def get_app_setting():
    setting, _ = AppSetting.objects.get_or_create(pk=1, defaults={"cycle_start_day": 1})
    return setting


#ログイン中の人のデータだけ取る
def get_preferred_categories(user):
    return Category.objects.filter(owner=user).annotate(
        expense_count=Count("expenses")
    ).order_by("-expense_count", "name", "id")

#月の開始日を自由にする
def get_cycle_range(target_date, cycle_start_day):
    current_month_last_day = monthrange(target_date.year, target_date.month)[1]
    this_month_start_day = min(cycle_start_day, current_month_last_day)
    this_month_anchor = date(target_date.year, target_date.month, this_month_start_day)

    if target_date >= this_month_anchor:
        start_date = this_month_anchor

        if target_date.month == 12:
            next_year = target_date.year + 1
            next_month = 1
        else:
            next_year = target_date.year
            next_month = target_date.month + 1

        next_month_last_day = monthrange(next_year, next_month)[1]
        next_start_day = min(cycle_start_day, next_month_last_day)
        end_date = date(next_year, next_month, next_start_day)

    else:
        if target_date.month == 1:
            prev_year = target_date.year - 1
            prev_month = 12
        else:
            prev_year = target_date.year
            prev_month = target_date.month - 1

        prev_month_last_day = monthrange(prev_year, prev_month)[1]
        prev_start_day = min(cycle_start_day, prev_month_last_day)
        start_date = date(prev_year, prev_month, prev_start_day)
        end_date = this_month_anchor

    return start_date, end_date


def get_month_navigation(year, month):  #前の月と次の月を計算する
    current_first = date(year, month, 1)  #今の月の1日を作る　基準日

    prev_last = current_first - timedelta(days=1) #1日前に戻る
    prev_year = prev_last.year   #年と月を取り出す　年またぎも自動で対応
    prev_month = prev_last.month

    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    return prev_year, prev_month, next_year, next_month

#URLやフォームの年月を安全な数字に変換する
def parse_year_month(year_str, month_str):
    today = timezone.localdate()

    try:
        year = int(year_str) if year_str else today.year
        month = int(month_str) if month_str else today.month
    except (TypeError, ValueError):
        return today.year, today.month

    if month < 1 or month > 12:
        month = today.month

    if year < 2000:
        year = today.year

    return year, month

#年の選択肢（プルダウン）を作る
def get_summary_year_choices(user, today_year):
    #データから年を取得　DBからこの人が使ってる年だけ取る
    expense_years = list(
        Expense.objects.filter(owner=user).dates("date", "year", order="ASC")
    )
    years = sorted({d.year for d in expense_years} | {today_year})

    if not years:   #初回データゼロでも動く
        base_year = today_year #一番新しい年を基準にする
    else:
        base_year = max(years)

    start_year = base_year - 3  #前後3年くらいで
    end_year = base_year + 3

    return list(range(start_year, end_year + 1))

#絶対に安全な日付しか通さないフィルター
def parse_entry_date(date_str):
    today = timezone.localdate()  #今日の日付を取得

    if not date_str:    #空チェック　今日の日付を使う
        return today

    try:
        parsed = date.fromisoformat(date_str)
    except ValueError:
        return today   #今日の日付を使う

    if parsed > today:  #未来日はありえない
        return today

    return parsed


@login_required
def index(request):
    categories = get_preferred_categories(request.user) #カテゴリ取得

    today = timezone.localdate()
    target_date = parse_entry_date(
        request.GET.get("date") or request.POST.get("entry_date")
    )

   #その日付の支出のうち、ログイン中ユーザーのものだけ
    selected_day_expenses = Expense.objects.filter(
        owner=request.user,
        date=target_date
    ).select_related("category").order_by("-created_at")

    selected_day_total = selected_day_expenses.aggregate(
        total=Sum("amount")
    )["total"] or 0
    selected_day_count = selected_day_expenses.count()

    prev_input_date = target_date - timedelta(days=1)
    next_input_date = target_date + timedelta(days=1)
    can_go_next = next_input_date <= today

    if request.method == "POST":
        amount = request.POST.get("amount")
        category_id = request.POST.get("category")
        entry_date = parse_entry_date(request.POST.get("entry_date"))

        if not amount:
            return render(request, "kakeibo/index.html", {
                "categories": categories,
                "today": today,
                "target_date": target_date,
                "selected_day_total": selected_day_total,
                "selected_day_count": selected_day_count,
                "prev_input_date": prev_input_date,
                "next_input_date": next_input_date,
                "can_go_next": can_go_next,
                "is_today_input_date": target_date == today,
                "error_message": "金額を入力してください。",
            })

        try:
            amount_int = int(float(amount))
        except ValueError:
            return render(request, "kakeibo/index.html", {
                "categories": categories,
                "today": today,
                "target_date": target_date,
                "selected_day_total": selected_day_total,
                "selected_day_count": selected_day_count,
                "prev_input_date": prev_input_date,
                "next_input_date": next_input_date,
                "can_go_next": can_go_next,
                "is_today_input_date": target_date == today,
                "error_message": "金額が正しくありません。",
            })

        if amount_int <= 0:
            return render(request, "kakeibo/index.html", {
                "categories": categories,
                "today": today,
                "target_date": target_date,
                "selected_day_total": selected_day_total,
                "selected_day_count": selected_day_count,
                "prev_input_date": prev_input_date,
                "next_input_date": next_input_date,
                "can_go_next": can_go_next,
                "is_today_input_date": target_date == today,
                "error_message": "金額を入力してください。",
            })

        if not category_id:
            return render(request, "kakeibo/index.html", {
                "categories": categories,
                "today": today,
                "target_date": target_date,
                "selected_day_total": selected_day_total,
                "selected_day_count": selected_day_count,
                "prev_input_date": prev_input_date,
                "next_input_date": next_input_date,
                "can_go_next": can_go_next,
                "is_today_input_date": target_date == today,
                "error_message": "項目を選択してください。",
            })

        category = get_object_or_404(Category, pk=category_id, owner=request.user)

        #ここでDBに入る
        Expense.objects.create(
            owner=request.user,
            category=category,
            amount=amount_int,
            date=entry_date,
        )

        return redirect(f"{request.path}?date={entry_date.isoformat()}")

    return render(request, "kakeibo/index.html", {
        "categories": categories,
        "today": today,
        "target_date": target_date,
        "selected_day_total": selected_day_total,
        "selected_day_count": selected_day_count,
        "prev_input_date": prev_input_date,
        "next_input_date": next_input_date,
        "can_go_next": can_go_next,
        "is_today_input_date": target_date == today,
    })

#入力された支出をDBに保存して、結果をJSONで返す
@login_required
#URLを直接開いて GET でアクセスした場合は、保存処理をしない
def ajax_add_expense(request):#Ajax保存 画面リロードなし
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST only"}, status=405)#405その方法ではつかえません

    amount = request.POST.get("amount")
    category_id = request.POST.get("category")
    entry_date = parse_entry_date(request.POST.get("entry_date"))

    if not amount:
        return JsonResponse({"success": False, "error": "金額を入力してください"}, status=400)#400送られた内容が正しくない

    try:
        amount_int = int(float(amount))
    except ValueError:
        return JsonResponse({"success": False, "error": "金額が正しくありません"}, status=400)
    #0以下を禁止
    if amount_int <= 0:
        return JsonResponse({"success": False, "error": "金額を入力してください"}, status=400)

    #項目未選択は禁止
    if not category_id:
        return JsonResponse({"success": False, "error": "項目を選択してください"}, status=400)

    #カテゴリを取得する
    #そのカテゴリがログイン中のユーザーのものか
    category = get_object_or_404(Category, pk=category_id, owner=request.user)

    #ここで実際にDBへ保存
    expense = Expense.objects.create(
        owner=request.user,   #誰のデータか
        category=category,    #どの項目か
        amount=amount_int,    #いくらか
        date=entry_date,      #いつの支出か
    )

    #保存後、すぐ
    # その日の再集計をする
    selected_day_qs = Expense.objects.filter(owner=request.user, date=entry_date)
    selected_day_total = selected_day_qs.aggregate(total=Sum("amount"))["total"] or 0
    selected_day_count = selected_day_qs.count()

    today = timezone.localdate() #今日かどうか

    return JsonResponse({
        #保存成功
        "success": True,
        "expense_id": expense.id,
        #保存した内容
        "amount": expense.amount,
        "category_name": category.name,
        "date": expense.date.isoformat(),
        #画面の表示更新に使う
        "selected_day_total": selected_day_total,
        "selected_day_count": selected_day_count,
        "selected_date": entry_date.isoformat(),
        "selected_date_display": f"{entry_date.month}/{entry_date.day}",
        "is_today_input_date": entry_date == today, #今の入力が今日か、フロント側に教える
        #フロント側でトーストや演出を出すための材料
        "toast": {
            "message": "追加しました",
            "type": "created",
            "duration": 2600,
        }
    })


@login_required
#カテゴリ一覧を表示して、設定も更新できる
def category_list(request):
    setting = get_app_setting() #必ず1件ある設定を取得

    if request.method == "POST": #POSTなら設定更新
        cycle_form = AppSettingForm(request.POST, instance=setting)#既存のsettingを更新する
        if cycle_form.is_valid(): #フォームのチェック
            cycle_form.save() #DB更新
            flash_updated(request, "集計開始日を更新しました")
            return redirect("kakeibo:category_list")
    else:
        cycle_form = AppSettingForm(instance=setting)#現在の値をフォームに入れる
    #自分のカテゴリだけ、カテゴリごとの使用回数を数えてる
    categories = Category.objects.filter(owner=request.user).annotate(
        expense_count=Count("expenses")
    ).order_by("-expense_count", "name", "id")#よく使う順

    category_count = categories.count()#件数表示用

    return render(request, "kakeibo/category_list.html", {
        "categories": categories,                   #一覧表示用
        "category_count": category_count,           #○件
        "cycle_form": cycle_form,                   #入力欄
        "cycle_start_day": setting.cycle_start_day, #現在の設定　表示用
    })

#カテゴリを新規作成する画面＋保存処理
@login_required
def category_create(request):
    #このユーザーが初めてカテゴリ作るかどうか 初回だけ動きを変える
    existing_count = Category.objects.filter(owner=request.user).count()
    is_first_category = (existing_count == 0)

    if request.method == "POST":
        form = CategoryForm(request.POST, request.FILES)#画像は今後使う予定
        if form.is_valid():#文字数OK？必須項目OK？
            category = form.save(commit=False)#まだDBに保存しない
            category.owner = request.user #ユーザー紐づけ
            category.save()#
            #ここでDBに保存
            flash_created(request, "項目を追加しました")

            #最初だけ入力画面に飛ばす
            if is_first_category:
                return redirect("kakeibo:index")
            return redirect("kakeibo:category_list")#2回目以降は普通に一覧に戻る
        else:
            print("CATEGORY CREATE ERRORS:", form.errors)#デバック用

    else:
        form = CategoryForm()#空フォーム送信

    return render(request, "kakeibo/category_form.html", {
        "form": form,              #入力欄
        "page_title": "項目を追加", #見出し
        "is_first_category": is_first_category,
    })

#指定したカテゴリを表示して、編集して、保存する
@login_required
#自分のカテゴリだけ
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk, owner=request.user)

    if request.method == "POST":#編集画面で内容を変えて「保存」を押したときにここに
        #既存カテゴリを更新する
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():#必須項目・文字数・型は正しいか
            category = form.save(commit=False)#DBに保存しないで、いったんPython側で受け取る
            category.owner = request.user #ユーザー紐づけ
            category.save()#既存カテゴリの上書き更新
            flash_updated(request, "更新しました")
            return redirect("kakeibo:category_list")#更新後はカテゴリ一覧画面へ
        else:
            print("CATEGORY EDIT ERRORS:", form.errors)

    else:
        form = CategoryForm(instance=category)#今の入力内容に上書き

    return render(request, "kakeibo/category_form.html", {
        "form": form,                 #フォーム全体
        "page_title": "項目を編集",    #
        "category": category,         #テンプレート側で使いたい時用
        "is_first_category": False,   #初回導線の分岐は不要なので
    })


@login_required
#自分のカテゴリしか削除できない
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, owner=request.user)

    if request.method == "POST":    #POSTなら本当に削除
        category.delete()
        flash_deleted(request, "削除しました")
        return redirect("kakeibo:category_list")#削除後はカテゴリ一覧に戻す

    return render(request, "kakeibo/category_confirm_delete.html", {
        "category": category,
    })

#1日単位の支出一覧と合計を表示する画面処理
@login_required
#1日の履歴
def history(request):
    selected_date = request.GET.get("date")#日付を受け取る

    #日付を安全に変換
    if selected_date:
        try:
            target_date = date.fromisoformat(selected_date)
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()

    #指定日の、自分のデータだけ　カテゴリも一緒に取ってる
    expenses = Expense.objects.filter(
        owner=request.user,
        date=target_date
    ).select_related("category").order_by("-created_at")#新しいのが上

    #その日の合計金額　データ0なら0円
    total_amount = expenses.aggregate(total=Sum("amount"))["total"] or 0

    #前日と翌日を作る
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)

    return render(request, "kakeibo/history.html", {
        "expenses": expenses,                      #その日の支出一覧
        "selected_date": target_date.isoformat(),  #文字列の日付
        "target_date": target_date,                #date型の日付
        "total_amount": total_amount,              #その日の合計
        "prev_date": prev_date.isoformat(),        #前日に移動
        "next_date": next_date.isoformat(),        #翌日に移動
    })

#指定した月の支出を、日ごと＋カテゴリごとにまとめて表示する
@login_required
def month_history(request):
    today = timezone.localdate()

    #年月決める
    year_str = request.GET.get("year")
    month_str = request.GET.get("month")

    #なければ今月
    try:
        year = int(year_str) if year_str else today.year
        month = int(month_str) if month_str else today.month
    #エラー対策
    except ValueError:
        year = today.year
        month = today.month

    #この人の、この月のデータ全部
    expenses = Expense.objects.filter(
        owner=request.user,
        date__year=year,
        date__month=month
    ).select_related("category").order_by("-date", "-created_at")#カテゴリも一緒に　新しい順

    #日ごとにまとめる
    grouped = defaultdict(list)
    daily_totals = {}
    category_totals = defaultdict(int)
    #ループ
    for expense in expenses:
        day = expense.date
        grouped[day].append(expense)
        category_totals[expense.category.name] += expense.amount #カテゴリごと集計

    #日ごとの合計
    for day, items in grouped.items():
        daily_totals[day] = sum(item.amount for item in items)

    #新しい順に並べ替え
    grouped_expenses = sorted(grouped.items(), reverse=True)
    #全部合計
    month_total = expenses.aggregate(total=Sum("amount"))["total"] or 0
    #前月計算
    prev_month_date = date(year, month, 1) - timedelta(days=1)
    #次月計算(12月だけ特別処理)
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    #金額が多い順
    category_totals_sorted = sorted(
        category_totals.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return render(request, "kakeibo/month_history.html", {
        "year": year,                              #年
        "month": month,                            #月
        "grouped_expenses": grouped_expenses,      #日ごとのデータ
        "daily_totals": daily_totals,
        "month_total": month_total,                #月合計
        "category_totals": category_totals_sorted, #カテゴリ合計
        "prev_year": prev_month_date.year,         #ナビ用
        "prev_month": prev_month_date.month,
        "next_year": next_year,
        "next_month": next_month,
    })

#指定した支出を編集して、元いた画面へ戻す処理
@login_required
#URLで指定されたID　ログイン中のユーザーの支出だけ
def expense_edit(request, pk):
    expense = get_object_or_404(
        Expense.objects.select_related("category"), #支出に紐づくカテゴリも一緒に取得しておく
        pk=pk,
        owner=request.user
    )
    #どの画面から来たか、どの年月日を見ていたかを覚える
    return_to = request.GET.get("return_to") or request.POST.get("return_to") or "history"
    back_date = request.GET.get("date") or request.POST.get("back_date") or request.POST.get("date") or ""
    back_year = request.GET.get("year") or request.POST.get("back_year") or request.POST.get("year") or ""
    back_month = request.GET.get("month") or request.POST.get("back_month") or request.POST.get("month") or ""

    if request.method == "POST":  #POSTなら更新処理
        #自分の支出を、自分のカテゴリ候補で編集する
        form = ExpenseEditForm(request.POST, instance=expense, user=request.user)
        if form.is_valid():
            updated_expense = form.save(commit=False)#まだDB保存しない

            #そのカテゴリの持ち主が本当にログイン中ユーザーか確認
            if updated_expense.category.owner != request.user:
                messages.error(request, "不正な項目です")
                return redirect("kakeibo:history")

            #ここで実際にDB更新
            updated_expense.owner = request.user
            updated_expense.save()

            flash_updated(request, "更新しました")

            #戻り先を分岐
            #集計画面から来た場合は集計画面へ戻す
            if return_to == "summary":
                if back_year and back_month:
                    return redirect(f"/summary/?year={back_year}&month={back_month}")
                return redirect("kakeibo:summary")

            #月履歴から来た場合は月一覧画面に戻す
            if return_to == "month_history":
                if back_year and back_month:
                    return redirect(f"/month-history/?year={back_year}&month={back_month}")
                return redirect("kakeibo:month_history")

            #日別一覧から来た場合、その日付の利益画面へ戻す
            if back_date:
                return redirect(f"/history/?date={back_date}")
            return redirect("kakeibo:history")
    #GETならフォームを表示 既存データ見ながら修正できる
    else:
        form = ExpenseEditForm(instance=expense, user=request.user)

    return render(request, "kakeibo/expense_form.html", {
        "form": form,              #編集フォーム
        "expense": expense,        #編集対象の支出
        "page_title": "履歴編集",   #画面タイトル
        "return_to": return_to,    #戻り先情報
        "back_date": back_date,
        "back_year": back_year,
        "back_month": back_month,
    })


@login_required
def expense_delete(request, pk):
    expense = get_object_or_404(
        Expense.objects.select_related("category"),
        pk=pk,
        owner=request.user
    )
    #どの画面から来たか
    return_to = request.GET.get("return_to") or request.POST.get("return_to") or "history"
    back_date = request.GET.get("date") or request.POST.get("back_date") or request.POST.get("date") or ""
    back_year = request.GET.get("year") or request.POST.get("back_year") or request.POST.get("year") or ""
    back_month = request.GET.get("month") or request.POST.get("back_month") or request.POST.get("month") or ""

    if request.method == "POST":
        expense.delete()
        flash_deleted(request, "削除しました")

        if return_to == "summary":
            if back_year and back_month:
                return redirect(f"/summary/?year={back_year}&month={back_month}")
            return redirect("kakeibo:summary")

        if return_to == "month_history":
            if back_year and back_month:
                return redirect(f"/month-history/?year={back_year}&month={back_month}")
            return redirect("kakeibo:month_history")

        if back_date:
            return redirect(f"/history/?date={back_date}")
        return redirect("kakeibo:history")

    return render(request, "kakeibo/expense_confirm_delete.html", {
        "expense": expense,
        "return_to": return_to,
        "back_date": back_date,
        "back_year": back_year,
        "back_month": back_month,
    })

#今日と今月の合計金額をJSONで返す
@login_required
def get_summary(request):
    today = timezone.localdate() #今日の日付
    setting = get_app_setting() #集計開始日を取得
    #今月の範囲を決める
    cycle_start, cycle_end = get_cycle_range(today, setting.cycle_start_day)

    #自分だけの、今日の合計
    today_total = Expense.objects.filter(
        owner=request.user,
        date=today
    ).aggregate(total=Sum("amount"))["total"] or 0

    #今月の合計
    month_total = Expense.objects.filter(
        owner=request.user,
        date__gte=cycle_start,
        date__lt=cycle_end
    ).aggregate(total=Sum("amount"))["total"] or 0

    #JSONで返す
    return JsonResponse({
        "today_total": today_total,
        "month_total": month_total,
    })

#集計画面
@login_required
def summary(request):
    #今日の日付と、設定を取得
    today = timezone.localdate()
    setting = get_app_setting()

    #表示する年月を決める
    selected_year, selected_month = parse_year_month(
        request.GET.get("year"),
        request.GET.get("month"),
    )

    #その月の基準日を決める
    target_date = date(selected_year, selected_month, 1)

    #集計期間を決める
    cycle_start, cycle_end = get_cycle_range(target_date, setting.cycle_start_day)
    #自分だけ、今日だけの支出をとる
    today_expenses = Expense.objects.filter(
        owner=request.user,
        date=today
    ).select_related("category").order_by("-created_at")

    #今日の合計と件数
    today_total = today_expenses.aggregate(total=Sum("amount"))["total"] or 0
    today_count = today_expenses.count()

    #今見ている月の集計対象すべて取得
    cycle_expenses = Expense.objects.filter(
        owner=request.user,
        date__gte=cycle_start,
        date__lt=cycle_end
    ).select_related("category").order_by("-date", "-created_at")

    #月の合計と件数
    month_total = cycle_expenses.aggregate(total=Sum("amount"))["total"] or 0
    month_count = cycle_expenses.count()

    #日ごとにまとめる
    grouped_dict = defaultdict(list)
    for expense in cycle_expenses:
        grouped_dict[expense.date].append(expense)

    #テンプレートで使いやすい形に変換
    grouped_daily_expenses = []
    for day, items in sorted(grouped_dict.items(), reverse=True):
        day_total = sum(item.amount for item in items)
        grouped_daily_expenses.append({
            "date": day,          #日付
            "expenses": items,    #その日の明細
            "total": day_total,   #その日の合計
            "count": len(items),  #件数
        })

    raw_category_totals = (
        cycle_expenses
        .values("category", "category__name", "category__budget")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total", "category__name")
    )

#カテゴリ別合計をDS
    category_totals = []
    for item in raw_category_totals:
        budget = item["category__budget"] or 0
        total = item["total"] or 0

        if budget > 0:
            percent = round((total / budget) * 100, 1) #バーグラフ用　ここで割合計算
            bar_percent = min(percent, 100)
            is_over_budget = total > budget
        else:
            percent = 0
            bar_percent = 0
            is_over_budget = False

        category_totals.append({
            "category_id": item["category"],
            "category_name": item["category__name"],
            "count": item["count"],
            "total": total,
            "budget": budget,
            "percent": percent,
            "bar_percent": bar_percent,
            "is_over_budget": is_over_budget,
            "has_budget": budget > 0,
        })

    prev_year, prev_month, next_year, next_month = get_month_navigation(selected_year, selected_month)

    is_current_view = (selected_year == today.year and selected_month == today.month)
    year_choices = get_summary_year_choices(request.user, today.year)
    month_choices = list(range(1, 13))

    return render(request, "kakeibo/summary.html", {
        "today": today,
        "today_total": today_total,
        "today_count": today_count,

        "selected_year": selected_year,
        "selected_month": selected_month,
        "is_current_view": is_current_view,

        "month_total": month_total,
        "month_count": month_count,
        "cycle_start_date": cycle_start,
        "cycle_end_date": cycle_end - timedelta(days=1),
        "grouped_daily_expenses": grouped_daily_expenses,
        "category_totals": category_totals,

        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,

        "year_choices": year_choices,
        "month_choices": month_choices,
        "cycle_start_day": setting.cycle_start_day,
    })

#新規登録
def signup(request):
    if request.user.is_authenticated:
        return redirect("kakeibo:index")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) #登録後ログイン
            flash_created(request, "登録が完了しました")
            return redirect("kakeibo:index")
    else:
        form = SignUpForm()

    return render(request, "registration/signup.html", {"form": form})

#PWA（アプリ化）ホーム画面に追加
def pwa_manifest(request):
    manifest = f"""
{{
  "name": "SimpleLedger",
  "short_name": "SimpleLedger",
  "description": "スマホで素早く入力できる家計簿アプリ",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "background_color": "#171c25",
  "theme_color": "#171c25",
  "orientation": "portrait",
  "lang": "ja",
  "icons": [
    {{
      "src": "{static('icons/icon-192.png')}",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    }},
    {{
      "src": "{static('icons/icon-512.png')}",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }}
  ]
}}
""".strip()
    return HttpResponse(manifest, content_type="application/manifest+json")

#オフライン対応(画面だけ)
def service_worker(request):
    js = f"""

#このページを保存しとく
const CACHE_NAME = "simpleledger-v1";
const APP_SHELL = [
  "/",
  "/summary/",
  "/month-history/",
  "/history/",
  "/accounts/login/",
  "/accounts/signup/",
  "{static('icons/icon-192.png')}",
  "{static('icons/icon-512.png')}",
];

self.addEventListener("install", (event) => {{
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
}});

self.addEventListener("activate", (event) => {{
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
}});

self.addEventListener("fetch", (event) => {{
  const request = event.request;

  if (request.method !== "GET") return;

  event.respondWith(
    caches.match(request).then((cachedResponse) => {{
      if (cachedResponse) return cachedResponse;

      return fetch(request)
        .then((networkResponse) => {{
          if (
            request.url.startsWith(self.location.origin) &&
            networkResponse &&
            networkResponse.status === 200
          ) {{
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {{
              cache.put(request, responseClone);
            }});
          }}
          return networkResponse;
        }})
        .catch(() => {{
          return caches.match("/");
        }});
    }})
  );
}});
""".strip()
    return HttpResponse(js, content_type="application/javascript")