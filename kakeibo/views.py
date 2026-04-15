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


#フラッシュメッセージ（通知）
def flash_created(request, message):
    messages.success(request, message, extra_tags="created")


def flash_updated(request, message):
    messages.info(request, message, extra_tags="updated")


def flash_deleted(request, message):
    messages.error(request, message, extra_tags="deleted")


#アプリの設定を必ず1件取得する（なければ作る）
def get_app_setting():
    setting, _ = AppSetting.objects.get_or_create(pk=1, defaults={"cycle_start_day": 1})
    return setting

#ログイン中の人のデータだけ取る
def get_preferred_categories(user):
    return Category.objects.filter(owner=user).annotate(
        expense_count=Count("expenses")
    ).order_by("-expense_count", "name", "id")

#月の開始日を自由に決める
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

#前の月と次の月を計算する　今の月の１日(基準)をつくる
def get_month_navigation(year, month):
    current_first = date(year, month, 1)

    prev_last = current_first - timedelta(days=1) #前の月の最終日
    prev_year = prev_last.year    #年と月を取り出す　年またぎも対応
    prev_month = prev_last.month

    #12月だけ特別処理　年が変わるから
    if month == 12:
        next_year = year + 1
        next_month = 1
    #それ以外は普通に+1
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
    #エラー対策
    except (TypeError, ValueError):
        return today.year, today.month

    #月の範囲チェック
    if month < 1 or month > 12:
        month = today.month
    #年の範囲チェック
    if year < 2000:
        year = today.year

    return year, month


#年の選択肢（プルダウン）を作る
def get_summary_year_choices(user, today_year):
    #「この人が使ってる年」だけ取る
    expense_years = list(
        Expense.objects.filter(owner=user).dates("date", "year", order="ASC")
    )
    years = sorted({d.year for d in expense_years} | {today_year})

    #一番新しい年を基準にする
    if not years:
        base_year = today_year
    else:
        base_year = max(years)

    #前後３年くらいにした
    start_year = base_year - 3
    end_year = base_year + 3

    return list(range(start_year, end_year + 1))

#日付を安全に変換する（未来日は禁止）
def parse_entry_date(date_str):
    today = timezone.localdate()

    # 空チェック
    if not date_str:
        return today

    try:
        parsed = date.fromisoformat(date_str)
    except ValueError:
        return today

    # 家計簿だから、未来日は入れない
    if parsed > today:
        return today

    return parsed


@login_required
def index(request):
    categories = get_preferred_categories(request.user)#カテゴリ取得

    today = timezone.localdate()
    target_date = parse_entry_date(
        request.GET.get("date") or request.POST.get("entry_date")
    )

    #今日のデータ取得
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

    if request.method == "POST":  #ここで保存
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

    #HTMLにデータ渡して表示
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

#Ajax保存(入力された支出をDBに保存して、結果をJSONで返す)
#入力された支出を安全に保存して、画面更新に必要な情報をまとめて返す処理
@login_required
def ajax_add_expense(request):
    #保存処理はPOSTで 405→その方法では使えません
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST only"}, status=405)

    #金額・項目ID・入力日を受け取る　日付は空・不正な文字・未来日は今日に補正される
    amount = request.POST.get("amount")
    category_id = request.POST.get("category")
    entry_date = parse_entry_date(request.POST.get("entry_date"))

    #その方法では使えません 400→送られた内容が正しくない
    if not amount:
        return JsonResponse({"success": False, "error": "金額を入力してください"}, status=400)
    #金額を数値に変換　小数がきても、整数にして保存
    try:
        amount_int = int(float(amount))
    except ValueError:
        return JsonResponse({"success": False, "error": "金額が正しくありません"}, status=400)
    #0以下を禁止
    if amount_int <= 0:
        return JsonResponse({"success": False, "error": "金額を入力してください"}, status=400)


    #項目未選択を禁止
    if not category_id:
        return JsonResponse({"success": False, "error": "項目を選択してください"}, status=400)

    #ログイン中のユーザーのものか確認してからカテゴリを取得
    category = get_object_or_404(Category, pk=category_id, owner=request.user)
    #ここで実際にDBに保存　支出データを新しく作る本体
    expense = Expense.objects.create(
        owner=request.user,  #誰のデータ
        category=category,   #どの項目
        amount=amount_int,   #いくらか
        date=entry_date,     #いつの支出
    )
    #保存したら、その日の合計と件数をすぐ再計算して返す
    selected_day_qs = Expense.objects.filter(owner=request.user, date=entry_date)
    selected_day_total = selected_day_qs.aggregate(total=Sum("amount"))["total"] or 0
    selected_day_count = selected_day_qs.count()

    #今日かどうか　フロント側へ伝えて画面表示の分岐にする
    today = timezone.localdate()

    return JsonResponse({
        #保存成功
        "success": True,
        "expense_id": expense.id,
        #何を保存したか
        "amount": expense.amount,
        "category_name": category.name,
        "date": expense.date.isoformat(),
        #画面の表示更新に使う
        "selected_day_total": selected_day_total,
        "selected_day_count": selected_day_count,
        "selected_date": entry_date.isoformat(),
        "selected_date_display": f"{entry_date.month}/{entry_date.day}",
        "is_today_input_date": entry_date == today,
        #フロント側でトーストや演出を出すための材料
        "toast": {
            "message": "追加しました",
            "type": "created",
            "duration": 2600,
        }
    })

#カテゴリ一覧を表示しつつ、設定も更新できる画面
@login_required
def category_list(request):
    setting = get_app_setting()  #必ず1件ある設定を取得

    if request.method == "POST":  #POSTなら設定更新
        #既存のsettingを更新する
        cycle_form = AppSettingForm(request.POST, instance=setting)
        #1~31の範囲か？数字か？
        if cycle_form.is_valid():
            #DB更新
            cycle_form.save()
            #トースト表示
            flash_updated(request, "集計開始日を更新しました")
            return redirect("kakeibo:category_list")

    #現在の値をフォームに入れる
    else:
        cycle_form = AppSettingForm(instance=setting)

    #自分のカテゴリだけ
    categories = Category.objects.filter(owner=request.user).annotate(
        expense_count=Count("expenses")  #カテゴリごとの使用回数を追加
    ).order_by("-expense_count", "name", "id")  #よく使うカテゴリが上に

    category_count = categories.count()  #件数

    #テンプレートに渡す
    return render(request, "kakeibo/category_list.html", {
        "categories": categories,                   #一覧表示
        "category_count": category_count,           #〇件
        "cycle_form": cycle_form,                   #入力欄
        "cycle_start_day": setting.cycle_start_day, #表示用
    })


#カテゴリを新規作成する画面＋保存処理
@login_required
def category_create(request):
    #このユーザーが初めてカテゴリをつくるかどうか　初回だけ動きを変えるため
    existing_count = Category.objects.filter(owner=request.user).count()
    is_first_category = (existing_count == 0)

    if request.method == "POST":  #POSTなら保存処理
        #フォーム作成　画像は今後使う
        form = CategoryForm(request.POST, request.FILES)
        #文字数、必須項目OK？
        if form.is_valid():
            category = form.save(commit=False)  #まだDBに保存しない
            category.owner = request.user       #ユーザーの紐づけするから
            category.save()                     #ここで初めてDBに保存
            flash_created(request, "項目を追加しました")

            #初回だけ入力画面に飛ばす　最初はすぐ入力したいから
            if is_first_category:
                return redirect("kakeibo:index")
            #２回目以降はふつうに一覧に戻る
            return redirect("kakeibo:category_list")
        else:
            print("CATEGORY CREATE ERRORS:", form.errors)#デバック用

    #GET時(初期表示)　空フォームを表示
    else:
        form = CategoryForm()

    #テンプレートへ渡す
    return render(request, "kakeibo/category_form.html", {
        "form": form,                           #入力欄
        "page_title": "項目を追加",              #見出し
        "is_first_category": is_first_category, #初回フラグ
    })


#自分のカテゴリだけを安全に編集する更新処理(既存データを書き換える)
@login_required
def category_edit(request, pk):  #pk = ID
    #指定されたIDのカテゴリ＆ログイン中のユーザーのカテゴリだけ
    category = get_object_or_404(Category, pk=pk, owner=request.user)

    #ユーザーが編集画面で内容を変えて「保存」を押したときここに入る
    if request.method == "POST":
        #フォームに既存データを結びつける
        #instance=category があることで、新規作成じゃなくて、既存カテゴリを更新
        form = CategoryForm(request.POST, request.FILES, instance=category)
        #必須項目ある？文字数正しい？型は合ってる？
        if form.is_valid():
            category = form.save(commit=False)  #まだDB保存しない
            #このカテゴリの持ち主はログイン中ユーザーと明示
            category.owner = request.user
            category.save()  #ここで実際にDB更新
            flash_updated(request, "更新しました")
            return redirect("kakeibo:category_list")  #カテゴリ一覧画面へ戻す
        else:
            print("CATEGORY EDIT ERRORS:", form.errors)

    #GETなら初期表示(今のカテゴリ名＆設定値が入った状態で表示)
    else:
        form = CategoryForm(instance=category)

    return render(request, "kakeibo/category_form.html", {
        "form": form,                #編集フォーム全体
        "page_title": "項目を編集",   #画面mタイトル
        "category": category,        #テンプレート側で現在のカテゴリ情報を使いたいとき用
        "is_first_category": False,  #初回導線の分岐はここでは不要なのでFalse固定
    })

#カテゴリを削除するための確認画面と削除処理
@login_required
def category_delete(request, pk):
    #URLで指定されたカテゴリID＆ログイン中ユーザーのカテゴリだけ探す
    category = get_object_or_404(Category, pk=pk, owner=request.user)

    #POSTなら本当に削除
    if request.method == "POST":
        category.delete()  #delete() を呼ぶことで、そのカテゴリをDBから消す
        flash_deleted(request, "削除しました")  #削除後の通知
        return redirect("kakeibo:category_list")  #削除後はカテゴリ一覧に戻す

    #GETなら確認画面(POSTでなければ、まだ削除しない)
    return render(request, "kakeibo/category_confirm_delete.html", {
        "category": category,
    })

#1日単位の支出一覧と合計を表示する画面処理
@login_required
def history(request):
    selected_date = request.GET.get("date")  #これはURLのクエリから日付を取ってる

#日付があれば文字列→date型に　変な形式or指定なしなら今日にする
    if selected_date:
        try:
            target_date = date.fromisoformat(selected_date)
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()


#自分のデータ＆指定日のデータだけ　カテゴリも一緒に取得
    expenses = Expense.objects.filter(
        owner=request.user,
        date=target_date
    ).select_related("category").order_by("-created_at")  #新しいのが上に

    #その日の合計金額も計算
    total_amount = expenses.aggregate(total=Sum("amount"))["total"] or 0

    #日付ナビ用　前日・翌日だから、基準日から１日ずらす
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)

    #テンプレートに渡す
    return render(request, "kakeibo/history.html", {
        "expenses": expenses,                     #その日の支出一覧
        "selected_date": target_date.isoformat(), #文字列の日付
        "target_date": target_date,               #date型の日付
        "total_amount": total_amount,             #その日の合計
        "prev_date": prev_date.isoformat(),       #前日・翌日への移動用
        "next_date": next_date.isoformat(),
    })



#月の一覧(指定した月の支出を、日ごと＋カテゴリごとにまとめて表示する)
@login_required
def month_history(request):
    today = timezone.localdate()

    #年月決める()URLから取得
    year_str = request.GET.get("year")
    month_str = request.GET.get("month")

    #数値に変換
    try:
        year = int(year_str) if year_str else today.year
        month = int(month_str) if month_str else today.month
    #エラー対策
    except ValueError:
        year = today.year
        month = today.month

    #この人のこの月のデータ全部取得
    expenses = Expense.objects.filter(
        owner=request.user,
        date__year=year,
        date__month=month
    #カテゴリも一緒に取る　　新しい日→古い日に　同じ日なら新しい入力順
    ).select_related("category").order_by("-date", "-created_at")

    #日毎にまとめる
    grouped = defaultdict(list)
    daily_totals = {}
    category_totals = defaultdict(int)
    #ループ
    for expense in expenses:
        day = expense.date
        grouped[day].append(expense)
        #同時にカテゴリごと集計
        category_totals[expense.category.name] += expense.amount

    #日毎の合計
    for day, items in grouped.items():
        daily_totals[day] = sum(item.amount for item in items)
    #日付の新しい順に
    grouped_expenses = sorted(grouped.items(), reverse=True)
    #月の合計
    month_total = expenses.aggregate(total=Sum("amount"))["total"] or 0

    #前月計算
    prev_month_date = date(year, month, 1) - timedelta(days=1)
    if month == 12:             #12月だけ特別処理
        next_year = year + 1
        next_month = 1
    else:                       #通常時は普通に
        next_year = year
        next_month = month + 1
    #金額が多い順に
    category_totals_sorted = sorted(
        category_totals.items(),
        key=lambda x: x[1],
        reverse=True
    )
    #テンプレートに渡す
    return render(request, "kakeibo/month_history.html", {
        "year": year,                              #年月
        "month": month,
        "grouped_expenses": grouped_expenses,      #日毎のデータ
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
def expense_edit(request, pk):
    #URLで指定された支出ID＆ログイン中ユーザーの支出だけ取得
    expense = get_object_or_404(
        Expense.objects.select_related("category"),#支出に紐づくカテゴリも一緒に取得
        pk=pk,
        owner=request.user
    )
    #どこから来たか　どの年月日を見ていたか覚えてる(戻り先・日付情報)
    return_to = request.GET.get("return_to") or request.POST.get("return_to") or "history"
    back_date = request.GET.get("date") or request.POST.get("back_date") or request.POST.get("date") or ""
    back_year = request.GET.get("year") or request.POST.get("back_year") or request.POST.get("year") or ""
    back_month = request.GET.get("month") or request.POST.get("back_month") or request.POST.get("month") or ""

    if request.method == "POST":  #保存ボタンを押した後の処理
        #自分の支出を、自分のカテゴリ候補で編集するフォームをつくる
        form = ExpenseEditForm(request.POST, instance=expense, user=request.user)
        #日付の形式・必須入力・カテゴリの整合性などをチェック
        if form.is_valid():
            updated_expense = form.save(commit=False)  #まだDB保存しない
            #そのカテゴリの持ち主が本当にログインユーザーなのか確認
            if updated_expense.category.owner != request.user:
                messages.error(request, "不正な項目です")
                return redirect("kakeibo:history")
            #ここで実際にDB更新
            updated_expense.owner = request.user
            updated_expense.save()

            flash_updated(request, "更新しました")

            #戻り先の分岐
            #集計画面から来たなら、その時見ていた集計画面に戻す
            if return_to == "summary":
                if back_year and back_month:
                    return redirect(f"/summary/?year={back_year}&month={back_month}")
                return redirect("kakeibo:summary")


            #月履歴から来ていたら、見ていた年月の一覧画面に戻す
            if return_to == "month_history":
                if back_year and back_month:
                    return redirect(f"/month-history/?year={back_year}&month={back_month}")
                return redirect("kakeibo:month_history")


            #日ごと履歴から来たなら、見ていた同じ日へ戻す
            if back_date:
                return redirect(f"/history/?date={back_date}")
            return redirect("kakeibo:history")
    #編集画面を最初に開いたとき　既存データ入りのフォーム
    else:
        form = ExpenseEditForm(instance=expense, user=request.user)

    #テンプレートへ渡す
    return render(request, "kakeibo/expense_form.html", {
        "form": form,              #編集フォーム
        "expense": expense,        #編集対象の支出
        "page_title": "履歴編集",   #画面タイトル
        "return_to": return_to,    #戻り先情報
        "back_date": back_date,
        "back_year": back_year,
        "back_month": back_month,
    })

#どの画面から来たかを覚えたまま、削除後に元の場所へ戻す
@login_required
def expense_delete(request, pk):
    expense = get_object_or_404(
        Expense.objects.select_related("category"),
        pk=pk,
        owner=request.user
    )

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


@login_required
def get_summary(request):
    today = timezone.localdate()
    setting = get_app_setting()
    cycle_start, cycle_end = get_cycle_range(today, setting.cycle_start_day)

    today_total = Expense.objects.filter(
        owner=request.user,
        date=today
    ).aggregate(total=Sum("amount"))["total"] or 0

    month_total = Expense.objects.filter(
        owner=request.user,
        date__gte=cycle_start,
        date__lt=cycle_end
    ).aggregate(total=Sum("amount"))["total"] or 0

    return JsonResponse({
        "today_total": today_total,
        "month_total": month_total,
    })


#選んだ月の集計画面に必要なデータを全部作って、summary.html に渡す処理
#集計画面
@login_required
def summary(request):
    today = timezone.localdate()  #今日の日付
    setting = get_app_setting()  #アプリ設定

    #URLから年月を受け取って、安全な年月に変換
    selected_year, selected_month = parse_year_month(
        request.GET.get("year"),
        request.GET.get("month"),
    )
    #その月の基準日をつくる
    target_date = date(selected_year, selected_month, 1)
    #集計期間を決める
    cycle_start, cycle_end = get_cycle_range(target_date, setting.cycle_start_day)
    #自分・今日だけの支出一覧取る　
    today_expenses = Expense.objects.filter(
        owner=request.user,
        date=today
    ).select_related("category").order_by("-created_at")
    #今日の合計と件数
    today_total = today_expenses.aggregate(total=Sum("amount"))["total"] or 0
    today_count = today_expenses.count()
    #集計期間内の支出を取得
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
            "date": day,
            "expenses": items,
            "total": day_total,
            "count": len(items),
        })

#カテゴリ別合計をDBで集計
    raw_category_totals = (
        cycle_expenses
        .values("category", "category__name", "category__budget")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total", "category__name")
    )
    #バーグラフ用に予算・実際の合計を取り出す
    category_totals = []
    for item in raw_category_totals:
        budget = item["category__budget"] or 0
        total = item["total"] or 0

        #予算がある場合の割合計算
        if budget > 0:
            percent = round((total / budget) * 100, 1)  #実際の割合
            bar_percent = min(percent, 100)  #バー表示用　100％で頭打ち
            is_over_budget = total > budget  #予算オーバーかどうか

        #予算がない場合　割合ないので0扱い　ゼロ除算防ぐ
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
    #前月・次月ナビつくる
    prev_year, prev_month, next_year, next_month = get_month_navigation(selected_year, selected_month)

    #今見てるのが今月か判定　テンプレート側での分岐に使う
    is_current_view = (selected_year == today.year and selected_month == today.month)
    #年月の選択肢をつくる　プルダウン用
    year_choices = get_summary_year_choices(request.user, today.year)
    month_choices = list(range(1, 13))

    #テンプレートへ全部渡す
    return render(request, "kakeibo/summary.html", {
        "today": today,                                   #今日の情報
        "today_total": today_total,
        "today_count": today_count,

        "selected_year": selected_year,                   #見ている年月
        "selected_month": selected_month,
        "is_current_view": is_current_view,

        "month_total": month_total,                        #月集計
        "month_count": month_count,
        "cycle_start_date": cycle_start,
        "cycle_end_date": cycle_end - timedelta(days=1),

        "grouped_daily_expenses": grouped_daily_expenses,  #日ごとの履歴
        "category_totals": category_totals,                #カテゴリ別集計

        "prev_year": prev_year,                            #前後ナビ
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,

        "year_choices": year_choices,                       #プルダウン
        "month_choices": month_choices,
        "cycle_start_day": setting.cycle_start_day,
    })


#新規ユーザーを登録して、そのままログインさせる処理
def signup(request):
    #すでにログインしてるか(ログイン済みなら登録画面に入れない)
    if request.user.is_authenticated:
        return redirect("kakeibo:index")

    if request.method == "POST":       #新規登録ボタン押したとき
        #ユーザー入力データをフォームに入れる
        form = SignUpForm(request.POST)
        #ユーザー名重複・パスワード条件・必須項目　全部OK？
        if form.is_valid():

            user = form.save()  #新しいユーザーをここでDBに保存
            login(request, user)  #作ったユーザーで即ログイン
            flash_created(request, "登録が完了しました")  #トースト通知
            return redirect("kakeibo:index")  #登録完了後、アプリ開始画面へ

    #初めて開いた時は空のフォーム
    else:
        form = SignUpForm()
    #テンプレート表示
    return render(request, "registration/signup.html", {"form": form})


#アプリの設定ファイル（manifest.json）を返す処理
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