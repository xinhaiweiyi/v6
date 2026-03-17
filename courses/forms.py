from django import forms

from courses.models import Category, Chapter, Course, Lesson


def apply_control_style(field, textarea=False, file_input=False):
    if file_input:
        field.widget.attrs.setdefault(
            "class",
            "file-input file-input-bordered w-full rounded-lg border-slate-200 bg-white",
        )
        return
    if isinstance(field.widget, forms.Select):
        field.widget.attrs.setdefault(
            "class",
            "select select-bordered h-11 w-full rounded-lg border-slate-200 bg-white",
        )
        return
    if textarea:
        field.widget.attrs.setdefault(
            "class",
            "textarea textarea-bordered min-h-[140px] w-full rounded-lg border-slate-200 bg-white",
        )
        return
    field.widget.attrs.setdefault(
        "class",
        "input input-bordered h-11 w-full rounded-lg border-slate-200 bg-white",
    )


class CourseForm(forms.ModelForm):
    remove_cover = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        apply_control_style(self.fields["title"])
        apply_control_style(self.fields["category"])
        self.fields["cover"].widget = forms.FileInput()
        apply_control_style(self.fields["cover"], file_input=True)
        self.fields["cover"].widget.attrs.setdefault("accept", "image/*")
        self.fields["remove_cover"].widget = forms.HiddenInput()
        self.fields["remove_cover"].initial = ""
        apply_control_style(self.fields["description"], textarea=True)

    class Meta:
        model = Course
        fields = ["title", "category", "cover", "description"]
        labels = {
            "title": "课程名称",
            "category": "课程分类",
            "cover": "课程封面",
            "description": "课程简介",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}


class ChapterForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_control_style(self.fields["title"])

    class Meta:
        model = Chapter
        fields = ["title"]
        labels = {"title": "章节名称"}


class LessonForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_control_style(self.fields["title"])
        apply_control_style(self.fields["video"], file_input=True)
        self.fields["video"].widget.attrs.setdefault("accept", "video/*")
        self.fields["duration_seconds"].required = False
        self.fields["duration_seconds"].initial = 0
        self.fields["duration_seconds"].widget = forms.HiddenInput()

    class Meta:
        model = Lesson
        fields = ["title", "video", "duration_seconds"]
        labels = {
            "title": "视频标题",
            "video": "上传视频",
            "duration_seconds": "时长(秒)",
        }


class CategoryForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_control_style(self.fields["name"])
        self.fields["is_active"].widget.attrs.setdefault("class", "toggle toggle-success")

    class Meta:
        model = Category
        fields = ["name", "is_active"]
        labels = {"name": "分类名称", "is_active": "启用状态"}
