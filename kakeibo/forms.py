from django import forms
from .models import AppSetting, Category, Expense


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["category", "amount"]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(
                owner=user
            ).order_by("name")
        else:
            self.fields["category"].queryset = Category.objects.none()


class ExpenseEditForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["category", "amount", "date"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(
                owner=user
            ).order_by("name")
        else:
            self.fields["category"].queryset = Category.objects.none()


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "budget", "icon"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "項目名を入力",
            }),
            "budget": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "月予算を入力",
                "min": "0",
                "step": "1",
            }),
            "icon": forms.ClearableFileInput(attrs={
                "class": "form-control",
                "id": "id_icon",
                "accept": "image/*",
            }),
        }


class AppSettingForm(forms.ModelForm):
    class Meta:
        model = AppSetting
        fields = ["cycle_start_day"]
        widgets = {
            "cycle_start_day": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "1",
                "max": "31",
                "placeholder": "例: 25",
            }),
        }