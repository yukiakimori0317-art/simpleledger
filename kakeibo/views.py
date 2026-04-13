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


def flash_created(request, message):
    messages.success(request, message, extra_tags="created")


def flash_updated(request, message):
    messages.info(request, message, extra_tags="updated")


def flash_deleted(request, message):
    messages.error(request, message, extra_tags="deleted")


def get_app_setting():
    setting, _ = AppSetting.objects.get_or_create(pk=1, defaults={"cycle_start_day": 1})
    return setting


def get_preferred_categories(user):
    return Category.objects.filter(owner=user).annotate(
        expense_count=Count("expenses")
    ).order_by("-expense_count", "name", "id")


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


def get_month_navigation(year, month):
    current_first = date(year, month, 1)

    prev_last = current_first - timedelta(days=1)
    prev_year = prev_last.year
    prev_month = prev_last.month

    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    return prev_year, prev_month, next_year, next_month


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


def get_summary_year_choices(user, today_year):
    expense_years = list(
        Expense.objects.filter(owner=user).dates("date", "year", order="ASC")
    )
    years = sorted({d.year for d in expense_years} | {today_year})

    if not years:
        base_year = today_year
    else:
        base_year = max(years)

    start_year = base_year - 3
    end_year = base_year + 3

    return list(range(start_year, end_year + 1))


def parse_entry_date(date_str):
    today = timezone.localdate()

    if not date_str:
        return today

    try:
        parsed = date.fromisoformat(date_str)
    except ValueError:
        return today

    if parsed > today:
        return today

    return parsed


@login_required
def index(request):
    categories = get_preferred_categories(request.user)

    today = timezone.localdate()
    target_date = parse_entry_date(
        request.GET.get("date") or request.POST.get("entry_date")
    )

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


@login_required
def ajax_add_expense(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST only"}, status=405)

    amount = request.POST.get("amount")
    category_id = request.POST.get("category")
    entry_date = parse_entry_date(request.POST.get("entry_date"))

    if not amount:
        return JsonResponse({"success": False, "error": "金額を入力してください"}, status=400)

    try:
        amount_int = int(float(amount))
    except ValueError:
        return JsonResponse({"success": False, "error": "金額が正しくありません"}, status=400)

    if amount_int <= 0:
        return JsonResponse({"success": False, "error": "金額を入力してください"}, status=400)

    if not category_id:
        return JsonResponse({"success": False, "error": "項目を選択してください"}, status=400)

    category = get_object_or_404(Category, pk=category_id, owner=request.user)

    expense = Expense.objects.create(
        owner=request.user,
        category=category,
        amount=amount_int,
        date=entry_date,
    )

    selected_day_qs = Expense.objects.filter(owner=request.user, date=entry_date)
    selected_day_total = selected_day_qs.aggregate(total=Sum("amount"))["total"] or 0
    selected_day_count = selected_day_qs.count()

    today = timezone.localdate()

    return JsonResponse({
        "success": True,
        "expense_id": expense.id,
        "amount": expense.amount,
        "category_name": category.name,
        "date": expense.date.isoformat(),
        "selected_day_total": selected_day_total,
        "selected_day_count": selected_day_count,
        "selected_date": entry_date.isoformat(),
        "selected_date_display": f"{entry_date.month}/{entry_date.day}",
        "is_today_input_date": entry_date == today,
        "toast": {
            "message": "追加しました",
            "type": "created",
            "duration": 2600,
        }
    })


@login_required
def category_list(request):
    setting = get_app_setting()

    if request.method == "POST":
        cycle_form = AppSettingForm(request.POST, instance=setting)
        if cycle_form.is_valid():
            cycle_form.save()
            flash_updated(request, "集計開始日を更新しました")
            return redirect("kakeibo:category_list")
    else:
        cycle_form = AppSettingForm(instance=setting)

    categories = Category.objects.filter(owner=request.user).annotate(
        expense_count=Count("expenses")
    ).order_by("-expense_count", "name", "id")

    category_count = categories.count()

    return render(request, "kakeibo/category_list.html", {
        "categories": categories,
        "category_count": category_count,
        "cycle_form": cycle_form,
        "cycle_start_day": setting.cycle_start_day,
    })


@login_required
def category_create(request):
    existing_count = Category.objects.filter(owner=request.user).count()
    is_first_category = (existing_count == 0)

    if request.method == "POST":
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            category = form.save(commit=False)
            category.owner = request.user
            category.save()
            flash_created(request, "項目を追加しました")

            if is_first_category:
                return redirect("kakeibo:index")
            return redirect("kakeibo:category_list")
        else:
            print("CATEGORY CREATE ERRORS:", form.errors)

    else:
        form = CategoryForm()

    return render(request, "kakeibo/category_form.html", {
        "form": form,
        "page_title": "項目を追加",
        "is_first_category": is_first_category,
    })


@login_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk, owner=request.user)

    if request.method == "POST":
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            category = form.save(commit=False)
            category.owner = request.user
            category.save()
            flash_updated(request, "更新しました")
            return redirect("kakeibo:category_list")
        else:
            print("CATEGORY EDIT ERRORS:", form.errors)

    else:
        form = CategoryForm(instance=category)

    return render(request, "kakeibo/category_form.html", {
        "form": form,
        "page_title": "項目を編集",
        "category": category,
        "is_first_category": False,
    })


@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, owner=request.user)

    if request.method == "POST":
        category.delete()
        flash_deleted(request, "削除しました")
        return redirect("kakeibo:category_list")

    return render(request, "kakeibo/category_confirm_delete.html", {
        "category": category,
    })


@login_required
def history(request):
    selected_date = request.GET.get("date")

    if selected_date:
        try:
            target_date = date.fromisoformat(selected_date)
        except ValueError:
            target_date = timezone.localdate()
    else:
        target_date = timezone.localdate()

    expenses = Expense.objects.filter(
        owner=request.user,
        date=target_date
    ).select_related("category").order_by("-created_at")

    total_amount = expenses.aggregate(total=Sum("amount"))["total"] or 0

    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)

    return render(request, "kakeibo/history.html", {
        "expenses": expenses,
        "selected_date": target_date.isoformat(),
        "target_date": target_date,
        "total_amount": total_amount,
        "prev_date": prev_date.isoformat(),
        "next_date": next_date.isoformat(),
    })


@login_required
def month_history(request):
    today = timezone.localdate()

    year_str = request.GET.get("year")
    month_str = request.GET.get("month")

    try:
        year = int(year_str) if year_str else today.year
        month = int(month_str) if month_str else today.month
    except ValueError:
        year = today.year
        month = today.month

    expenses = Expense.objects.filter(
        owner=request.user,
        date__year=year,
        date__month=month
    ).select_related("category").order_by("-date", "-created_at")

    grouped = defaultdict(list)
    daily_totals = {}
    category_totals = defaultdict(int)

    for expense in expenses:
        day = expense.date
        grouped[day].append(expense)
        category_totals[expense.category.name] += expense.amount

    for day, items in grouped.items():
        daily_totals[day] = sum(item.amount for item in items)

    grouped_expenses = sorted(grouped.items(), reverse=True)

    month_total = expenses.aggregate(total=Sum("amount"))["total"] or 0

    prev_month_date = date(year, month, 1) - timedelta(days=1)
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    category_totals_sorted = sorted(
        category_totals.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return render(request, "kakeibo/month_history.html", {
        "year": year,
        "month": month,
        "grouped_expenses": grouped_expenses,
        "daily_totals": daily_totals,
        "month_total": month_total,
        "category_totals": category_totals_sorted,
        "prev_year": prev_month_date.year,
        "prev_month": prev_month_date.month,
        "next_year": next_year,
        "next_month": next_month,
    })


@login_required
def expense_edit(request, pk):
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
        form = ExpenseEditForm(request.POST, instance=expense, user=request.user)
        if form.is_valid():
            updated_expense = form.save(commit=False)

            if updated_expense.category.owner != request.user:
                messages.error(request, "不正な項目です")
                return redirect("kakeibo:history")

            updated_expense.owner = request.user
            updated_expense.save()

            flash_updated(request, "更新しました")

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
    else:
        form = ExpenseEditForm(instance=expense, user=request.user)

    return render(request, "kakeibo/expense_form.html", {
        "form": form,
        "expense": expense,
        "page_title": "履歴編集",
        "return_to": return_to,
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


@login_required
def summary(request):
    today = timezone.localdate()
    setting = get_app_setting()

    selected_year, selected_month = parse_year_month(
        request.GET.get("year"),
        request.GET.get("month"),
    )

    target_date = date(selected_year, selected_month, 1)

    cycle_start, cycle_end = get_cycle_range(target_date, setting.cycle_start_day)

    today_expenses = Expense.objects.filter(
        owner=request.user,
        date=today
    ).select_related("category").order_by("-created_at")

    today_total = today_expenses.aggregate(total=Sum("amount"))["total"] or 0
    today_count = today_expenses.count()

    cycle_expenses = Expense.objects.filter(
        owner=request.user,
        date__gte=cycle_start,
        date__lt=cycle_end
    ).select_related("category").order_by("-date", "-created_at")

    month_total = cycle_expenses.aggregate(total=Sum("amount"))["total"] or 0
    month_count = cycle_expenses.count()

    grouped_dict = defaultdict(list)
    for expense in cycle_expenses:
        grouped_dict[expense.date].append(expense)

    grouped_daily_expenses = []
    for day, items in sorted(grouped_dict.items(), reverse=True):
        day_total = sum(item.amount for item in items)
        grouped_daily_expenses.append({
            "date": day,
            "expenses": items,
            "total": day_total,
            "count": len(items),
        })

    raw_category_totals = (
        cycle_expenses
        .values("category", "category__name", "category__budget")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total", "category__name")
    )

    category_totals = []
    for item in raw_category_totals:
        budget = item["category__budget"] or 0
        total = item["total"] or 0

        if budget > 0:
            percent = round((total / budget) * 100, 1)
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


def signup(request):
    if request.user.is_authenticated:
        return redirect("kakeibo:index")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            flash_created(request, "登録が完了しました")
            return redirect("kakeibo:index")
    else:
        form = UserCreationForm()

    return render(request, "registration/signup.html", {"form": form})


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