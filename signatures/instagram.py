# Instagram Screen Signatures
# Ported from ig-automation's battle-tested signature definitions
#
# 40+ screens covering:
# - Overlays (comments, likes, peek view)
# - Navigation (explore, search, profile, home, DMs)
# - Content viewing (reels, stories, posts)
# - Content creation (post/reel/story flow)
# - Login flow (TOS, login, 2FA, save info)
# - Onboarding (Facebook, contacts, profile pic, follow suggestions)
#
# Selector Format (Clone-Safe):
# - ":id/element_id" matches ANY package prefix
# - "text:exact text" for text content
# - "content-desc:label" for accessibility labels
# - "contains:substring" for partial matches

from typing import List, Dict, Set
from .base import ScreenSignature, register_signatures

# App identifier
APP_ID = "instagram"

# Safe states for warmup operations
WARMUP_SAFE_STATES: Set[str] = {
    "explore_grid",
    "search_results_reels",
    "reel_viewing",
}

# Safe states for login success
LOGIN_SAFE_STATES: Set[str] = {
    "home_feed",
    "explore_grid",
    "search_results_reels",
    "reel_viewing",
    "onboarding_facebook_suggestions",
    "onboarding_contacts_sync",
    "onboarding_profile_picture",
    "onboarding_follow_people",
    "onboarding_add_email",
    "onboarding_preferences",
}

# Overlay screens (can appear on top of other screens)
OVERLAY_SCREENS: Set[str] = {
    "peek_view",
    "comments_view",
    "likes_page",
}

# =============================================================================
# SCREEN SIGNATURES
# =============================================================================

INSTAGRAM_SIGNATURES: List[ScreenSignature] = [
    # -------------------------------------------------------------------------
    # OVERLAYS (Priority 90-100) - Check these first, they appear on top
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="peek_view",
        description="Long-press preview overlay showing reel/post with action buttons",
        required=[":id/peek_container"],
        forbidden=[
            ":id/layout_comment_thread_edittext",
            "text:Views & likes",
        ],
        unique=[":id/peek_container"],
        optional=[
            ":id/peek_view_group_buttons",
            ":id/row_feed_button_like",
            ":id/row_feed_button_share",
            "content-desc:View Profile",
            "content-desc:Like",
        ],
        priority=100,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="comments_view",
        description="Bottom sheet comments overlay on reel/post",
        required=[
            ":id/layout_comment_thread_edittext",
            ":id/bottom_sheet_container",
        ],
        forbidden=["text:Views & likes"],
        unique=[":id/layout_comment_thread_edittext"],
        optional=[
            "text:Comments",
            ":id/comment_composer_parent",
            ":id/main_list_view",
            "content-desc:Tap to like comment",
        ],
        priority=95,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="likes_page",
        description="Views & likes overlay showing users who liked content",
        required=[
            ":id/bottom_sheet_container",
            "text:Likes",
        ],
        forbidden=[
            ":id/layout_comment_thread_edittext",
            ":id/peek_container",
        ],
        optional=[
            ":id/row_user_container_base",
            ":id/row_follow_button",
            "content-desc:Likes",
        ],
        priority=98,
        recovery_action="back",
        is_safe_state=False,
    ),

    # -------------------------------------------------------------------------
    # CRITICAL SCREENS (Priority 80-89)
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="account_suspended",
        description="Account suspended/disabled - terminal state",
        required=["contains:days left to appeal"],
        forbidden=[
            ":id/login_username",
            "text:Your story",
            "text:Get started",
        ],
        unique=["contains:days left to appeal"],
        optional=[
            "text:Appeal",
            "contains:suspended your account",
            "text:Why this happened",
        ],
        priority=95,
        recovery_action="handle_account_suspended",
        is_safe_state=False,
    ),

    # -------------------------------------------------------------------------
    # LOGIN FLOW (Priority 80-85)
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="join_instagram",
        description="Welcome screen with Get started / I already have an account",
        required=[
            "text:Get started",
            "text:I already have an account",
        ],
        forbidden=[
            ":id/login_username",
            "text:Meta Terms and Privacy Policy",
            "text:Your story",
        ],
        unique=["text:I already have an account"],
        optional=["text:English (US)"],
        priority=85,
        recovery_action="click_already_have_account",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="login_meta_tos",
        description="Meta Terms of Service acceptance screen",
        required=["text:Meta Terms and Privacy Policy"],
        forbidden=[
            ":id/login_username",
            ":id/password",
            "text:Your story",
        ],
        unique=["text:Meta Terms and Privacy Policy"],
        optional=[
            "text:Continue",
            "text:Privacy Policy",
            "content-desc:Continue",
        ],
        priority=80,
        recovery_action="click_continue",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="login_page",
        description="Main login form with username/password fields",
        required=[
            "content-desc:Username, email or mobile number",
            "content-desc:Password",
        ],
        forbidden=[
            ":id/profile_header_container",
            "text:Your story",
            "text:Meta Terms and Privacy Policy",
        ],
        unique=["content-desc:Username, email or mobile number"],
        optional=[
            "text:Log in",
            "text:Create new account",
            "text:Forgot password?",
        ],
        priority=80,
        recovery_action=None,
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="login_approval_required",
        description="Waiting for approval from another device",
        required=["text:Waiting for approval"],
        forbidden=[
            ":id/profile_header_container",
            "text:Your story",
            "content-desc:Username, email or mobile number",
        ],
        unique=["text:Waiting for approval"],
        optional=[
            "text:Try another way",
            "text:Check your notifications on another device",
        ],
        priority=81,
        recovery_action="click_try_another_way",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="login_2fa_method_select",
        description="Choose 2FA verification method",
        required=["text:Choose a way to confirm it's you"],
        forbidden=[
            ":id/profile_header_container",
            "text:Your story",
            "text:Waiting for approval",
        ],
        unique=["text:Choose a way to confirm it's you"],
        optional=[
            "text:Authentication app",
            "text:Backup code",
            "text:Continue",
        ],
        priority=81,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="login_2fa_code_entry",
        description="Enter 6-digit 2FA code from authenticator",
        required=["contains:6-digit code"],
        forbidden=[
            ":id/profile_header_container",
            "text:Your story",
            "text:Choose a way to confirm",
        ],
        unique=["contains:6-digit code"],
        optional=[
            "text:Code",
            "text:Continue",
            "text:Go to your authentication app",
        ],
        priority=82,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="login_save_info",
        description="Save your login info prompt after login",
        required=["text:Save your login info?"],
        forbidden=[
            ":id/profile_header_container",
            "text:Your story",
            "contains:6-digit code",
        ],
        unique=["text:Save your login info?"],
        optional=[
            "text:Save",
            "text:Not now",
        ],
        priority=82,
        recovery_action="click_not_now",
        is_safe_state=False,
    ),

    # -------------------------------------------------------------------------
    # ONBOARDING (Priority 83-84)
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="onboarding_facebook_suggestions",
        description="Connect to Facebook to find friends",
        required=["text:Get Facebook suggestions"],
        forbidden=[
            ":id/profile_header_container",
            "text:Your story",
            "text:Save your login info?",
        ],
        unique=[":id/find_friends_container"],
        optional=["text:Skip", "text:Continue"],
        priority=83,
        recovery_action="click_skip",
        is_safe_state=True,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="onboarding_contacts_sync",
        description="Sync contacts to find friends",
        required=["contains:allow access to your contacts"],
        forbidden=[
            ":id/profile_header_container",
            "text:Your story",
            "text:Get Facebook suggestions",
        ],
        unique=[":id/connect_contacts_sync_button"],
        optional=["text:Next"],
        priority=83,
        recovery_action="click_next",
        is_safe_state=True,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="onboarding_profile_picture",
        description="Add profile picture prompt",
        required=["contains:Add a profile picture"],
        forbidden=[
            ":id/profile_header_container",
            "text:Your story",
            "text:Get Facebook suggestions",
        ],
        unique=["text:Add a profile picture so your friends know it's you."],
        optional=["text:Add picture", "text:Skip"],
        priority=84,
        recovery_action="click_skip",
        is_safe_state=True,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="onboarding_follow_people",
        description="Try following 5+ people suggestion",
        required=["text:Try following 5+ people"],
        forbidden=[
            ":id/profile_header_container",
            "text:Your story",
            "text:Add a profile picture",
        ],
        unique=["content-desc:Try following 5+ people"],
        optional=["text:Skip", "text:Follow"],
        priority=84,
        recovery_action="click_skip",
        is_safe_state=True,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="onboarding_add_email",
        description="Add email address for recovery",
        required=["text:Add an email address"],
        forbidden=[
            ":id/profile_header_container",
            "text:Your story",
            "text:Try following 5+ people",
        ],
        unique=[":id/add_email_form"],
        optional=["text:Skip", "text:Next"],
        priority=84,
        recovery_action="click_skip",
        is_safe_state=True,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="onboarding_preferences",
        description="See more of what you love - content preferences",
        required=["text:See more of what you love"],
        forbidden=[
            ":id/profile_header_container",
            "text:Your story",
            "text:Add an email address",
        ],
        unique=[":id/reels_tuning_container"],
        optional=["text:Skip", "text:Next"],
        priority=84,
        recovery_action="click_skip",
        is_safe_state=True,
    ),

    # -------------------------------------------------------------------------
    # NAVIGATION SCREENS (Priority 25-55)
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="explore_grid",
        description="Search/Explore landing page with grid content",
        required=[":id/action_bar_search_edit_text"],
        forbidden=[
            ":id/profile_header_container",
            ":id/layout_comment_thread_edittext",
            ":id/peek_container",
            "text:Your story",
            ":id/action_bar_button_back",
            ":id/scrollable_tab_layout",
        ],
        unique=[":id/explore_action_bar"],
        optional=[
            ":id/explore_action_bar_container",
            "content-desc:Search and explore",
            "contains:Reel by",
        ],
        priority=40,
        recovery_action=None,
        is_safe_state=True,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="search_results_accounts",
        description="Search results showing Accounts tab",
        required=[
            ":id/action_bar_button_back",
            ":id/scrollable_tab_layout",
        ],
        forbidden=[
            ":id/explore_action_bar",
            ":id/profile_header_container",
            ":id/peek_container",
            "text:Your story",
            "contains:Reel by",
        ],
        unique=[":id/row_search_user_container"],
        optional=[
            ":id/row_search_user_username",
            "text:Accounts",
            "text:Reels",
        ],
        priority=50,
        recovery_action="click_explore",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="search_results_reels",
        description="Search results showing Reels content - IDEAL for warmup",
        required=[
            ":id/action_bar_button_back",
            ":id/scrollable_tab_layout",
            "contains:Reel by",
        ],
        forbidden=[
            ":id/explore_action_bar",
            ":id/profile_header_container",
            ":id/peek_container",
            ":id/layout_comment_thread_edittext",
            "text:Your story",
        ],
        optional=[
            ":id/action_bar_search_edit_text",
            ":id/play_count_container",
            "text:Reels",
        ],
        priority=55,
        recovery_action=None,
        is_safe_state=True,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="profile_page",
        description="User profile page (own or others)",
        required=[":id/profile_header_container"],
        forbidden=[
            ":id/action_bar_search_edit_text",
            ":id/clips_viewer_view_pager",
            ":id/layout_comment_thread_edittext",
            ":id/row_search_user_container",
            "text:Your story",
        ],
        unique=[":id/profile_header_container"],
        optional=[
            ":id/profile_tab_layout",
            ":id/profile_header_bio_text",
            "content-desc:Edit profile",
            "content-desc:Follow",
        ],
        priority=35,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="home_feed",
        description="Main Instagram feed - navigate away for warmup",
        required=[":id/row_feed_button_like"],  # Feed post like button - visible when viewing posts
        forbidden=[
            ":id/action_bar_search_edit_text",
            ":id/profile_header_container",
            ":id/clips_viewer_view_pager",
            ":id/layout_comment_thread_edittext",
        ],
        unique=[
            ":id/row_feed_button_like",
        ],
        optional=[
            "text:Your story",
            ":id/main_feed_action_bar",
            ":id/title_logo",
            ":id/action_bar_inbox_button",
            "content-desc:reels tray container",
            ":id/feed_preview_keep_watching_button",  # Reel overlay in feed
            ":id/row_feed_button_comment",
            ":id/row_feed_button_share",
            ":id/row_feed_button_save",
            ":id/media_group",
        ],
        priority=25,
        recovery_action="click_explore",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="notifications",
        description="Activity/notifications screen",
        required=[":id/newsfeed_you"],
        forbidden=[
            ":id/action_bar_search_edit_text",
            ":id/profile_header_container",
            ":id/clips_viewer_view_pager",
            "text:Your story",
        ],
        unique=[":id/newsfeed_you"],
        optional=[
            "text:Notifications",
            "text:Today",
            "text:Yesterday",
        ],
        priority=30,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="dm_inbox",
        description="Direct messages inbox",
        required=[":id/inbox_refreshable_thread_list_recyclerview"],
        forbidden=[
            ":id/action_bar_search_edit_text",
            ":id/profile_header_container",
            ":id/clips_viewer_view_pager",
            ":id/newsfeed_you",
            "text:Your story",
        ],
        unique=[":id/inbox_refreshable_thread_list_recyclerview"],
        optional=[
            ":id/row_inbox_container",
            "text:Primary",
            "content-desc:New Message",
        ],
        priority=30,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="dm_thread",
        description="Individual DM conversation",
        required=[":id/message_list"],
        forbidden=[
            ":id/inbox_refreshable_thread_list_recyclerview",
            ":id/action_bar_search_edit_text",
            ":id/profile_header_container",
            ":id/clips_viewer_view_pager",
        ],
        unique=[
            ":id/message_list",
            ":id/thread_fragment_container",
        ],
        optional=[
            ":id/row_thread_composer_container",
            ":id/row_thread_composer_edittext",
            "content-desc:Back",
        ],
        priority=32,
        recovery_action="back",
        is_safe_state=False,
    ),

    # -------------------------------------------------------------------------
    # CONTENT VIEWING (Priority 20-35)
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="reel_viewing",
        description="Full-screen reel player - main warmup state",
        required=[":id/clips_viewer_view_pager"],
        forbidden=[
            ":id/action_bar_search_edit_text",
            ":id/scrollable_tab_layout",
            ":id/layout_comment_thread_edittext",
            ":id/peek_container",
            "text:Views & likes",
            "text:Your story",
        ],
        unique=[":id/clips_viewer_view_pager"],
        optional=[
            ":id/like_button",
            ":id/comment_button",
            ":id/clips_author_username",
            ":id/clips_caption_component",
            "content-desc:Like OR content-desc:Unlike",
            "contains:Reel by",
        ],
        priority=30,
        recovery_action=None,
        is_safe_state=True,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="story_viewing",
        description="Full-screen story viewer",
        required=[":id/reel_viewer_root"],
        forbidden=[
            ":id/clips_viewer_view_pager",
            ":id/action_bar_search_edit_text",
            ":id/layout_comment_thread_edittext",
            ":id/profile_header_container",
            "text:Your story",
        ],
        unique=[":id/reel_viewer_root"],
        optional=[
            ":id/reel_viewer_progress_bar",
            ":id/reel_viewer_header",
            ":id/story_comment_preview_container",
            "content-desc:Share",
        ],
        priority=32,
        recovery_action="back",
        is_safe_state=False,
    ),

    # -------------------------------------------------------------------------
    # CONTENT CREATION (Priority 45-56)
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="create_post_gallery",
        description="Gallery picker for new post",
        required=[":id/gallery_picker_view"],
        forbidden=[
            ":id/clips_viewer_view_pager",
            ":id/reel_viewer_root",
            ":id/profile_header_container",
            ":id/layout_comment_thread_edittext",
        ],
        unique=[":id/gallery_picker_view"],
        optional=[
            ":id/media_picker_container",
            "text:New post",
            ":id/next_button_textview",
            "content-desc:POST",
            "content-desc:REEL",
        ],
        priority=50,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="create_post_editor",
        description="Post editing screen (filters, crop, text)",
        required=[":id/feed_post_capture_controls_container"],
        forbidden=[
            ":id/clips_action_bar",
            ":id/clips_viewer_view_pager",
            ":id/gallery_picker_view",
            ":id/profile_header_container",
            ":id/feed_publish_screen_caption_composer_container",
        ],
        unique=[":id/feed_post_capture_controls_container"],
        optional=[
            ":id/creation_bar_v2",
            "text:Filter",
            "text:Edit",
            "content-desc:Next",
        ],
        priority=51,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="create_post_share",
        description="Final share screen for posts",
        required=[
            ":id/feed_publish_screen_caption_composer_container",
            "text:New post",
        ],
        forbidden=[
            ":id/clips_viewer_view_pager",
            ":id/clips_action_bar",
            ":id/profile_header_container",
            "text:New reel",
        ],
        unique=["text:New post"],
        optional=[
            ":id/caption_input_text_view",
            "text:Share",
            "text:Add music",
        ],
        priority=56,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="create_story_camera",
        description="Camera screen for story creation",
        required=[
            ":id/camera_shutter_button",
            ":id/camera_destination_picker_container",
        ],
        forbidden=[
            ":id/gallery_picker_view",
            ":id/clips_viewer_view_pager",
            ":id/clips_top_level_container",
            ":id/reel_viewer_root",
            ":id/profile_header_container",
        ],
        unique=[":id/camera_shutter_button"],
        optional=[
            ":id/cam_dest_feed",
            ":id/cam_dest_clips",
            "content-desc:STORY",
            "content-desc:Shutter",
        ],
        priority=52,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="create_reel_camera",
        description="Camera/gallery screen for reel creation",
        required=[":id/clips_top_level_container"],
        forbidden=[
            ":id/clips_viewer_view_pager",
            ":id/reel_viewer_root",
            ":id/profile_header_container",
            ":id/camera_shutter_button",
        ],
        unique=[":id/clips_top_level_container"],
        optional=[
            ":id/cam_dest_clips",
            "text:New reel",
            "text:Templates",
            "content-desc:REEL",
        ],
        priority=53,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="create_reel_editor",
        description="Reel editing screen (audio, stickers, text, effects)",
        required=[":id/clips_action_bar"],
        forbidden=[
            ":id/clips_viewer_view_pager",
            ":id/clips_top_level_container",
            ":id/reel_viewer_root",
            ":id/profile_header_container",
            ":id/gallery_picker_view",
        ],
        unique=[":id/clips_action_bar"],
        optional=[
            ":id/clips_post_capture_controls",
            "text:Edit video",
            "text:Next",
            "content-desc:Add audio",
        ],
        priority=54,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="create_reel_music",
        description="Music selection bottom sheet for reels",
        required=[":id/music_search_clips_landing_page_container"],
        forbidden=[
            ":id/clips_viewer_view_pager",
            ":id/clips_top_level_container",
            ":id/profile_header_container",
            ":id/gallery_picker_view",
        ],
        unique=[":id/music_search_clips_landing_page_container"],
        optional=[
            ":id/bottom_sheet_container",
            "text:Search music",
            "text:For you",
            "text:Trending",
        ],
        priority=96,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="create_reel_text",
        description="Text overlay composer for reels",
        required=[":id/text_composer_fragment_container"],
        forbidden=[
            ":id/clips_viewer_view_pager",
            ":id/clips_action_bar",
            ":id/music_search_clips_landing_page_container",
            ":id/profile_header_container",
        ],
        unique=[":id/text_composer_fragment_container"],
        optional=[
            ":id/text_composer_edit_text",
            ":id/done_button",
            "content-desc:Done",
            "content-desc:Text color",
        ],
        priority=97,
        recovery_action="back",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="create_reel_share",
        description="Final share screen for reels",
        required=[
            ":id/feed_publish_screen_caption_composer_container",
            "text:New reel",
        ],
        forbidden=[
            ":id/clips_viewer_view_pager",
            ":id/clips_action_bar",
            ":id/text_composer_fragment_container",
            ":id/music_search_clips_landing_page_container",
            ":id/profile_header_container",
            "text:New post",
        ],
        unique=["text:New reel"],
        optional=[
            ":id/caption_input_text_view",
            ":id/clip_thumbnail_layout",
            "text:Share",
            "text:Save draft",
        ],
        priority=55,
        recovery_action="back",
        is_safe_state=False,
    ),
]


# =============================================================================
# RECOVERY PATHS - How to get back to safe states
# =============================================================================

RECOVERY_PATHS: Dict[str, Dict] = {
    "peek_view": {
        "actions": [("press", "back")],
        "target": "explore_grid",
        "max_retries": 2,
    },
    "likes_page": {
        "actions": [("press", "back")],
        "target": "reel_viewing",
        "max_retries": 2,
    },
    "comments_view": {
        "actions": [("press", "back")],
        "target": "reel_viewing",
        "max_retries": 2,
    },
    "profile_page": {
        "actions": [("press", "back")],
        "target": "explore_grid",
        "max_retries": 3,
    },
    "home_feed": {
        "actions": [("click", "explore_tab")],
        "target": "explore_grid",
        "max_retries": 2,
    },
    "search_results_accounts": {
        "actions": [("click", "explore_tab")],
        "target": "explore_grid",
        "max_retries": 2,
    },
    "unknown": {
        "actions": [("press", "back"), ("click", "explore_tab")],
        "target": "explore_grid",
        "max_retries": 3,
    },
}


# =============================================================================
# LOGIN RECOVERY PATHS
# =============================================================================

LOGIN_RECOVERY_PATHS: Dict[str, Dict] = {
    "login_meta_tos": {
        "actions": [("click", "continue")],
        "target": "login_page",
        "description": "Accept Meta Terms of Service",
    },
    "login_approval_required": {
        "actions": [("click", "try_another_way")],
        "target": "login_2fa_method_select",
        "description": "Click Try another way for alternative verification",
    },
    "login_2fa_method_select": {
        "actions": [("click", "auth_app")],
        "target": "login_2fa_code_entry",
        "description": "Select authentication app for 2FA",
    },
    "login_save_info": {
        "actions": [("click", "not_now")],
        "target": "home_feed",
        "description": "Skip saving login information",
    },
    "onboarding_facebook_suggestions": {
        "actions": [("click", "skip")],
        "target": "onboarding_contacts_sync",
        "description": "Skip Facebook friends suggestions",
    },
    "onboarding_contacts_sync": {
        "actions": [("press", "back")],
        "target": "onboarding_profile_picture",
        "description": "Skip contacts sync",
    },
    "onboarding_profile_picture": {
        "actions": [("click", "skip")],
        "target": "onboarding_follow_people",
        "description": "Skip profile picture setup",
    },
    "onboarding_follow_people": {
        "actions": [("click", "skip")],
        "target": "onboarding_add_email",
        "description": "Skip follow suggestions",
    },
    "onboarding_add_email": {
        "actions": [("click", "skip")],
        "target": "onboarding_preferences",
        "description": "Skip email setup",
    },
    "onboarding_preferences": {
        "actions": [("click", "skip")],
        "target": "home_feed",
        "description": "Skip content preferences",
    },
}


def register_instagram_signatures():
    """Register all Instagram signatures with the global registry."""
    register_signatures(APP_ID, INSTAGRAM_SIGNATURES)


# Auto-register on import
register_instagram_signatures()
