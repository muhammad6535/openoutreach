from django.contrib import admin
from django.contrib.admin import AdminSite
from django.db.models import Count
from django.utils.html import format_html

from chat.models import ChatMessage
from crm.models import Deal, Lead, Outcome
from linkedin.models import ActionLog, Campaign, LinkedInProfile, SearchKeyword, SiteConfig, Task


class OpenOutreachAdminSite(AdminSite):
    site_header = "OpenOutreach Admin"
    site_title = "OpenOutreach"
    index_title = "OpenOutreach Dashboard"

    def index(self, request, extra_context=None):
        from crm.models import Lead, Deal
        from linkedin.models import Task, Campaign

        extra_context = extra_context or {}
        extra_context["total_leads"] = Lead.objects.count()
        extra_context["active_leads"] = Lead.objects.filter(disqualified=False).count()
        extra_context["pending_tasks"] = Task.objects.filter(status="pending").count()
        extra_context["pending_deals"] = Deal.objects.filter(state__in=["Qualified", "Ready to Connect", "Pending"]).count()
        extra_context["campaigns"] = Campaign.objects.count()
        extra_context["failed_deals"] = Deal.objects.filter(state="Failed").count()
        return super().index(request, extra_context=extra_context)


admin_site = OpenOutreachAdminSite()


@admin.register(SiteConfig, site=admin_site)
class SiteConfigAdmin(admin.ModelAdmin):
    list_display = ("__str__", "llm_provider", "ai_model", "llm_api_base")
    fieldsets = (
        ("LLM Configuration", {
            "fields": ("llm_provider", "llm_api_key", "ai_model", "llm_api_base"),
            "description": "Settings for the LLM used by the agent (OpenAI-compatible, etc.)",
        }),
    )

    def has_add_permission(self, request):
        return not SiteConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Campaign, site=admin_site)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "deal_count", "is_freemium", "action_fraction")
    list_filter = ("is_freemium",)
    filter_horizontal = ("users",)
    fieldsets = (
        (None, {"fields": ("name", "users", "is_freemium")}),
        ("Agent Behavior", {
            "fields": ("action_fraction", "product_docs", "campaign_objective", "booking_link"),
            "description": "Control how the agent interacts with leads",
        }),
        ("Advanced", {
            "fields": ("seed_public_ids", "model_blob"),
            "classes": ("collapse",),
        }),
    )

    def deal_count(self, obj):
        return obj.deals.count()
    deal_count.short_description = "Deals"


@admin.register(LinkedInProfile, site=admin_site)
class LinkedInProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "linkedin_username", "active", "legal_accepted", "connect_daily_limit", "follow_up_daily_limit")
    list_filter = ("active", "legal_accepted")
    raw_id_fields = ("user", "self_lead")
    fieldsets = (
        (None, {"fields": ("user", "linkedin_username", "linkedin_password", "active")}),
        ("Limits", {"fields": ("connect_daily_limit", "follow_up_daily_limit")}),
        ("Legal", {"fields": ("legal_accepted", "subscribe_newsletter", "newsletter_processed")}),
        ("Session", {"fields": ("cookie_data", "self_lead"), "classes": ("collapse",)}),
    )


@admin.register(SearchKeyword, site=admin_site)
class SearchKeywordAdmin(admin.ModelAdmin):
    list_display = ("keyword", "campaign", "used", "used_at")
    list_filter = ("used", "campaign")
    raw_id_fields = ("campaign",)


@admin.register(ActionLog, site=admin_site)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ("action_type", "linkedin_profile", "campaign", "created_at")
    list_filter = ("action_type", "campaign")
    raw_id_fields = ("linkedin_profile", "campaign")
    date_hierarchy = "created_at"
    readonly_fields = ("linkedin_profile", "campaign", "action_type", "created_at")


@admin.register(Task, site=admin_site)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("task_type", "status", "scheduled_at", "campaign_id_display", "created_at")
    list_filter = ("task_type", "status")
    readonly_fields = ("task_type", "status", "scheduled_at", "started_at", "completed_at")
    date_hierarchy = "scheduled_at"

    def campaign_id_display(self, obj):
        cid = obj.payload.get("campaign_id") if obj.payload else None
        if cid:
            try:
                campaign = Campaign.objects.get(pk=cid)
                return campaign.name
            except Campaign.DoesNotExist:
                return f"Campaign #{cid}"
        return "-"
    campaign_id_display.short_description = "Campaign"


@admin.register(ChatMessage, site=admin_site)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("content_type", "object_id", "owner", "creation_date")
    list_filter = ("content_type", "owner")
    raw_id_fields = ("owner", "answer_to", "topic")
    date_hierarchy = "creation_date"
    readonly_fields = ("content_type", "object_id", "content", "owner", "creation_date")


@admin.register(Lead, site=admin_site)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("public_identifier", "deal_state", "disqualified", "creation_date")
    list_filter = ("disqualified",)
    search_fields = ("public_identifier", "linkedin_url")
    date_hierarchy = "creation_date"
    readonly_fields = ("urn", "creation_date", "update_date")

    def deal_state(self, obj):
        deal = Deal.objects.filter(lead=obj).first()
        if deal:
            color = {
                "Qualified": "orange",
                "Ready to Connect": "blue",
                "Pending": "purple",
                "Connected": "green",
                "Completed": "green",
                "Failed": "red",
            }.get(deal.state, "gray")
            return format_html('<span style="color: {};">{}</span>', color, deal.state)
        return "-"
    deal_state.short_description = "Deal State"


@admin.register(Deal, site=admin_site)
class DealAdmin(admin.ModelAdmin):
    list_display = ("lead_link", "state_colored", "campaign", "outcome", "connect_attempts", "creation_date")
    list_filter = ("state", "campaign", "outcome")
    search_fields = ("lead__public_identifier",)
    date_hierarchy = "creation_date"
    raw_id_fields = ("lead",)
    readonly_fields = ("creation_date", "update_date", "connect_attempts")
    fieldsets = (
        (None, {"fields": ("lead", "campaign", "state", "outcome", "reason")}),
        ("Connect", {"fields": ("connect_attempts", "backoff_hours", "next_check_pending_at")}),
        ("Summaries", {"fields": ("profile_summary", "chat_summary"), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("creation_date", "update_date")}),
    )

    def lead_link(self, obj):
        url = f"/admin/crm/lead/{obj.lead_id}/change/"
        return format_html('<a href="{}">{}</a>', url, obj.lead.public_identifier)
    lead_link.short_description = "Lead"

    def state_colored(self, obj):
        colors = {
            "Qualified": "orange",
            "Ready to Connect": "blue",
            "Pending": "purple",
            "Connected": "green",
            "Completed": "green",
            "Failed": "red",
        }
        c = colors.get(obj.state, "gray")
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', c, obj.state)
    state_colored.short_description = "State"
