from django import forms

from learning.models import Comment


class CommentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["content"].widget.attrs.setdefault(
            "class",
            "textarea textarea-bordered min-h-[120px] w-full rounded-2xl border-slate-200 bg-white",
        )

    class Meta:
        model = Comment
        fields = ["content"]
        labels = {"content": "评论内容"}
        widgets = {"content": forms.Textarea(attrs={"rows": 3, "placeholder": "请输入你的学习讨论..."})}
