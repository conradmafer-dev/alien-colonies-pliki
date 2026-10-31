extends Control

const RankingUIScript = preload("res://client/scripts/ranking_ui.gd")
var ranking_ui
var empire_name_ui
var play_update_progress: ProgressBar

const ReportNotificationsScript = preload("res://client/scripts/report_notifications.gd")
var report_notifications: Node

const FleetNavigationScript = preload ( "res://client/scripts/fleet_navigation.gd" )
const CommunicationsScript = preload ( "res://client/scripts/communications.gd" )
const AllianceUIScript = preload ( "res://client/scripts/alliance_ui.gd" )
const BeginnerGuideScript = preload ( "res://client/scripts/beginner_guide.gd" )
const PlanetStatusScript = preload ( "res://client/scripts/planet_status.gd" )
const PlayerActivityScript = preload ( "res://client/scripts/player_activity.gd" )
const CompactUIScript = preload ( "res://client/scripts/compact_ui.gd" )
const CatalogDetailsScript = preload ( "res://client/scripts/catalog_details.gd" )
const CatalogCarouselScript = preload ( "res://client/scripts/catalog_carousel.gd" )
const ResourceInfo = preload ( "res://client/scripts/resource_info.gd" )
const ReportResourceText = preload ( "res://client/scripts/report_resource_text.gd" )
const ResearchTreeScript = preload ( "res://client/scripts/research_tree.gd" )
const MegastructureUIScript = preload ( "res://client/scripts/megastructure_ui.gd" )
const PlanetaryUIScript = preload ( "res://client/scripts/planetary_ui.gd" )
const UIPreferencesScript = preload ( "res://client/scripts/ui_preferences.gd" )
const PlannedQueueUIScript = preload ( "res://client/scripts/planned_queue_ui.gd" )
const QueueBillingScript = preload ( "res://client/scripts/queue_billing.gd" )
const GoogleLoginScript = preload ( "res://client/scripts/google_login.gd" )
const LoginAnnouncementScript = preload ( "res://client/scripts/login_announcement.gd" )
const ReviewPromptScript = preload ( "res://client/scripts/review_prompt.gd" )
const EmailLoginScript = preload ( "res://client/scripts/email_login.gd" )

const SkillWheelScript = preload ( "res://client/scripts/skill_wheel.gd" )
const SkillIconScript = preload ( "res://client/scripts/skill_icon.gd" )
const GalaxyMapScript = preload ( "res://client/scripts/galaxy_map.gd" )
const GalaxyGuidanceModel = preload ( "res://client/scripts/galaxy_guidance_model.gd" )
const SwarmTargetScript = preload ( "res://client/scripts/swarm_target.gd" )
const PlanetArtScript = preload ( "res://client/scripts/planet_art.gd" )
const ServerAddressScript = preload ( "res://client/scripts/server_address.gd" )
const UpdatePolicyScript = preload ( "res://client/scripts/update_policy.gd" )
const SessionRevocationScript = preload ( "res://client/scripts/session_revocation.gd" )
const AuthTiming = preload ( "res://client/scripts/auth_timing.gd" )
const TouchScrollScript = preload ( "res://client/scripts/touch_scroll.gd" )
const InteractionGuardScript = preload ( "res://client/scripts/interaction_guard.gd" )
const MobileChoiceScript = preload ( "res://client/scripts/mobile_choice.gd" )
const MobileQuantityScript = preload ( "res://client/scripts/mobile_quantity.gd" )
const ReleasePanelScript = preload ( "res://client/scripts/release_panel.gd" )
const RaceTheme = preload ( "res://client/scripts/race_theme.gd" )
const ArtLibrary = preload ( "res://client/scripts/art_library.gd" )
const GAME_TITLE : String = "Alien Colonies"
const BRAND_ICON_PATH : String = "res://client/assets/alien_colonies_icon.png"
const LOGIN_BACKGROUND_PATH : String = "res://client/assets/alien_colonies_portrait.png"
const CLIENT_VERSION_CODE : int = 104
const CLIENT_VERSION_NAME : String = "0.12.37"
const PLAY_STORE_PACKAGE_ID : String = "com.conradmafer.aliencolonies"
const PLAY_STORE_WEB_URL : String = "https://play.google.com/store/apps/details?id=" + PLAY_STORE_PACKAGE_ID
const SERVER_CONFIG_PATH : String = "res://client/server_config.json"
const DEFAULT_SERVER_URL : String = "https://aliencolonies.com"
const LEGACY_OFFICIAL_SERVER_URL : String = "https://pogranicze-serwer-production.up.railway.app"
const HOST_OFFLINE_MESSAGE : String = "Sprawdź połączenie z internetem i spróbuj ponownie. Serwer może być chwilowo niedostępny."
const SERVER_CONFIG_ERROR_MESSAGE : String = "Nie udało się odczytać konfiguracji połączenia. Zainstaluj najnowszą wersję gry lub skontaktuj się z administratorem."
const NAV_LABELS : Array [ String ] = [ "PLANETA" , "GALAKTYKA" , "FLOTA" , "BADANIA" , "RAPORTY" ]
const SHIP_KEYS : Array [ String ] = [ "scout" , "cargo" , "colonizer" , "frigate" , "cruiser" ]
const MISSION_KEYS : Array [ String ] = [ "scout" , "colonize" , "attack" , "transport" , "expedition" ]
const MISSION_NAMES : Array [ String ] = [ "Zwiad" , "Kolonizacja" , "Atak" , "Transport" , "Ekspedycja" ]
const RESOURCE_KEYS : Array [ String ] = [ "metal" , "crystal" , "fuel" ]
const RESOURCE_NAMES : Dictionary = { "metal" : "METAL" , "crystal" : "KRYSZTAŁ" , "fuel" : "PALIWO" }
const NAMES : Dictionary = {
    "metal_mine" : "Kopalnia metalu" , "crystal_mine" : "Kopalnia kryształu" ,
    "refinery" : "Rafineria" , "power_plant" : "Elektrownia" , "shipyard" : "Stocznia" , "lab" : "Laboratorium" ,
    "propulsion" : "Napęd" , "weapons" : "Uzbrojenie" , "scout" : "Sonda" , "cargo" : "Transportowiec" ,
    "colonizer" : "Kolonizator" , "frigate" : "Fregata" , "cruiser" : "Krążownik" ,
    "interceptor" : "Przechwytywacz" , "siege" : "Okręt oblężniczy" , "freighter" : "Frachtowiec"
}

var fleet_navigation
var compact_ui
var project_ui
var planned_queue_ui
var queue_billing
var google_login
var email_login
var research_tree
var research_tree_header : VBoxContainer
var research_tree_scroll : ScrollContainer
var research_three_rows : bool = true
var research_layout_button : CheckButton
var megastructure_ui
var planetary_ui
var alliance_ui
var communications
var detailed_descriptions : bool = false
var detailed_descriptions_button : CheckButton
var interface_settings_path : String = UIPreferencesScript . SETTINGS_PATH
var swarm_hunt_settings_path : String = "user://swarm_hunt.cfg"
var swarm_hunt_generation : int = 0

var state : Dictionary = { }
var session_token : String = ""
var server_url : String = ""
var baked_server_url : String = ""
var server_override : bool = false
var server_config_error : String = ""
var session_config_path : String = "user://session.cfg"
var connection_editing : bool = false
var selected_planet : String = ""
var requested_planet : String = ""
var selected_system : String = ""
var selected_galaxy : String = "g1"
var galaxy_picker : MobileChoiceScript
var previous_galaxy_button : Button
var next_galaxy_button : Button
var galaxy_summary : Label
var galaxy_travel_note : Label
var galaxy_choices_signature : String = ""
var selected_target : String = ""
var selected_scout_system : String = ""
var current_tab : int = 0
var request_kind : String = ""
var request_pending : bool = false
var server_stamp : float = 0.0
var received_at_msec : int = 0
var clock_accumulator : float = 0.0
var own_signature : String = ""
var galaxy_signature : String = ""
var system_signature : String = ""
var reports_signature : String = ""
var fleets_signature : String = ""
var preview_fingerprint : String = ""
var preview_requested_fingerprint : String = ""
var preview_requested_world_signature : String = ""
var fleet_draft_generation : int = 0
var preview_requested_generation : int = 0
var quote_ready : bool = false
var refreshing : bool = false
var uncertain_action : Dictionary = { }
var update_required : bool = false
var update_manifest : Dictionary = { }
var dismissed_update_codes : Dictionary = { }
var update_request_pending : bool = false
var update_request_generation : int = 0
var showing_login : bool = true
var auth_timing_operation : String = ""
var auth_timing_prepare_ms : int = 0
var auth_timing_request_started : int = 0
var release_panel : ReleasePanelScript
var release_open : bool = false
var release_previous_back_quit : bool = true
var release_back_restore_pending : bool = false
var onboarding_card : Control
var onboarding_title : Label
var onboarding_description : Label
var onboarding_progress : ProgressBar
var onboarding_button : Button
var onboarding_skip : Button
var onboarding_resume : Button
var incoming_banner : Control
var incoming_summary : Label
var incoming_button : Button
var incoming_signature : String = ""
var report_store_path : String = "user://report_reads.cfg"
var report_scope : String = ""
var report_read_ids : Dictionary = { }
var unread_reports : int = 0

var http : HTTPRequest


class ResponseDecodeJob extends RefCounted:
    var kind: String = "state"
    var operation_kind: String
    var token: String
    var origin: String
    var generation: int
    var activity_ticket: int
    var result: int
    var response_code: int
    var arrived_msec: int
    var body: PackedByteArray
    var decoded: Variant
    var task_id: int = -1

    func decode(_keep_alive: RefCounted) -> void:
        # Pure JSON work only. No scene, control, renderer or host access here.
        decoded = JSON.parse_string(body.get_string_from_utf8())

var state_http : HTTPRequest
var response_decode_jobs: Array[ResponseDecodeJob] = []
var command_request_generation: int = 0
var state_request_pending : bool = false
var state_request_path : String = ""
var state_request_generation : int = 0
var player_activity = PlayerActivityScript . new ( )
var command_activity_ticket : int = 0
var state_activity_ticket : int = 0
var interaction_guard
var deferred_state : Dictionary = { }
var deferred_state_received_at : int = 0
var update_http : HTTPRequest
var update_timer : Timer
var update_overlay : Control
var update_margin : MarginContainer
var update_title : Label
var update_description : Label
var update_status : Label
var update_download_button : Button
var update_retry_button : Button
var update_later_button : Button
var poll_timer : Timer
var login_screen : Control
var login_margin : MarginContainer
var app_screen : MarginContainer
var server_field : LineEdit
var connection_setup : VBoxContainer
var connection_hint : Label
var default_server_button : Button
var name_field : LineEdit
var password_field : LineEdit
var login_message : Label
var login_buttons : Array [ Button ] = [ ]
var login_mode : String = ""
var login_scroll : ScrollContainer
var login_announcement
var review_prompt
var login_hero_spacer : Control
var login_form : VBoxContainer
var login_choice_panel : PanelContainer
var login_name_panel : PanelContainer
var login_name_background : ColorRect
var login_name_cancel : Button
var login_name_actions : HBoxContainer
var login_version_label : Label
var login_name_flow_check_queued : bool = false
var login_form_title : Label
var login_form_hint : Label
var login_submit : Button
var login_repeat_row : VBoxContainer
var repeat_password_field : LineEdit
var login_retry_button : Button
var login_notice : PanelContainer
var login_message_title : Label
var login_message_error : bool = false
var login_password_row : VBoxContainer
var google_login_button : Button
var create_account_button : Button
var email_login_button : Button
var email_form : VBoxContainer
var email_field : LineEdit
var email_send_button : Button
var email_cancel_button : Button
var email_wait_label : Label
var email_resend_button : Button
var email_entry_open : bool = false
var google_cancel_button : Button
var google_reauth_dialog : ConfirmationDialog
var google_reauth_status : Label
var email_reauth_dialog : ConfirmationDialog
var email_reauth_status : Label
var email_reauth_field : LineEdit
var connection_label : Label
var clock_label : Label
var planet_picker : MobileChoiceScript
var protection_label : Label
var resource_labels : Dictionary = { }
var storage_warning : Label
var tabs : Array [ ScrollContainer ] = [ ]
var tab_bodies : Array [ VBoxContainer ] = [ ]
var nav_buttons : Array [ Button ] = [ ]
var planet_title : Label
var planet_subtitle : Label
var energy_label : Label
var queue_label : Label
var building_list : BoxContainer
var building_carousel
var building_rows : Dictionary = { }
var inactive_racial_section : VBoxContainer
var inactive_racial_signature : String = ""
var unique_building_section : VBoxContainer
var unique_building_heading : Label
var unique_building_list : VBoxContainer
var building_heading : Label
var research_list : VBoxContainer
var research_rows : Dictionary = { }
var unique_research_section : VBoxContainer
var unique_research_heading : Label
var unique_research_list : VBoxContainer
var ship_list : BoxContainer
var ship_carousel
var defense_carousel
var ship_rows : Dictionary = { }
var defense_list : BoxContainer
var defense_rows : Dictionary = { }
var defense_section : VBoxContainer
var scout_age_labels : Array [ Dictionary ] = [ ]
var galaxy_map : Control
var system_picker : MobileChoiceScript
var planet_list : VBoxContainer
var mission_picker : MobileChoiceScript
var target_picker : MobileChoiceScript
var target_label : Label
var mission_hint : Label
var fleet_inputs : Dictionary = { }
var fleet_selection_list : VBoxContainer
var fleet_selection_rows : Dictionary = { }
var fleet_available : Dictionary = { }
var fleet_descriptions : Dictionary = { }
var cargo_inputs : Dictionary = { }
var cargo_box : VBoxContainer
var quote_label : Label
var preview_button : Button
var send_button : Button
var fleet_list : VBoxContainer
var fleet_mode : int = 1
var fleet_mode_bar : PanelContainer
var fleet_action_bar : PanelContainer
var fleet_mode_buttons : Array [ Button ] = [ ]
var fleet_active_button : Button
var fleet_missions_view : VBoxContainer
var fleet_build_view : VBoxContainer
var fleet_countdowns : Array [ Dictionary ] = [ ]
var report_list : VBoxContainer
var queue_name : String = ""
var queue_end : float = 0.0
var keyboard_baseline_height : int = 0
var mobile_insets : Vector4i = Vector4i ( 22 , 22 , 22 , 22 )
var ui_textures : Dictionary = { }
var energy_bar : ProgressBar
var production_label : Label
var queue_bar : ProgressBar
var queue_art : TextureRect
var queue_duration : float = 0.0
var queue_kind : String = ""
var queue_key : String = ""
var active_project : Control
var active_project_title : Label
var active_project_time : Label
var active_project_bar : ProgressBar
var cancel_project_button : Button
var cancel_project_dialog : ConfirmationDialog
var cancel_project_payload : Dictionary = { }
var connection_indicator : Label
var options_panel : VBoxContainer
var galaxy_overview : VBoxContainer
var galaxy_toggle : Button
var system_heading : Label
var system_coordinates : Label
var planet_actions : Array [ Dictionary ] = [ ]
var colony_illustration : TextureRect
var colony_panorama : Control
var biome_toggle : Button
var biome_expanded : bool = false
var race_screen : MarginContainer
var race_scroll : ScrollContainer
var race_cards : VBoxContainer
var race_status : Label
var race_retry_button : Button
var race_logout_button : Button
var race_buttons : Dictionary = { }
var race_signature : String = ""
var race_error_message : String = ""
var shipyard_heading : Label
var race_identity : Control
var race_portrait : TextureRect
var race_colony : TextureRect
var race_name : Label
var race_trait : Label
var race_weapon : Label
var fleet_portraits : Dictionary = { }
var fleet_names : Dictionary = { }
var fleet_header_art : TextureRect
var research_header_art : TextureRect
var skill_overlay : Control
var skill_margin : MarginContainer
var skill_wheel : Control
var skill_wallet_button : Button
var skill_wallet_label : Label
var skill_entry : Control
var skill_entry_summary : Label
var skill_entry_button : Button
var skill_detail_icon : Control
var skill_detail_title : Label
var skill_detail_scroll : ScrollContainer
var skill_detail_description : Label
var skill_detail_cost : Label
var skill_detail_status : Label
var skill_unlock_button : Button
var skill_retry_button : Button
var skill_selected_id : String = ""
var skill_message : String = ""
var skill_open : bool = false
var skill_previous_back_quit : bool = true
var skill_back_restore_pending : bool = false
var skill_hunt_button : Button
var pending_language : String = ""
var language_resume : Dictionary = { }


func _art_panel ( parent : Node , key : String , height : float ) -> Control :
    var panel : Control = Control . new ( )
    panel . custom_minimum_size . y = height if height > 0 else 220.0
    if height < 0 :

        panel . resized . connect ( func ( ) -> void : panel . custom_minimum_size . y = maxf ( 180.0 , panel . size . x * 2.0 / 3.0 ) )
    panel . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    panel . mouse_filter = Control . MOUSE_FILTER_IGNORE
    panel . clip_contents = true
    parent . add_child ( panel )
    var art : TextureRect = TextureRect . new ( )
    art . name = "Illustration"
    art . texture = ArtLibrary . texture ( key )
    art . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    art . expand_mode = TextureRect . EXPAND_IGNORE_SIZE
    art . stretch_mode = TextureRect . STRETCH_KEEP_ASPECT_COVERED
    art . mouse_filter = Control . MOUSE_FILTER_IGNORE
    panel . add_child ( art )
    var gradient : Gradient = Gradient . new ( )
    gradient . offsets = PackedFloat32Array ( [ 0.0 , 0.4 , 1.0 ] )
    gradient . colors = PackedColorArray ( [ _ui_color ( Color ( 0.03 , 0.067 , 0.051 , 0.0 ) ) , _ui_color ( Color ( 0.03 , 0.067 , 0.051 , 0.06 ) ) , _ui_color ( Color ( 0.03 , 0.067 , 0.051 , 0.94 ) ) ] )
    var fade : GradientTexture2D = GradientTexture2D . new ( )
    fade . gradient = gradient
    fade . fill_from = Vector2 ( 0 , 0 )
    fade . fill_to = Vector2 ( 0 , 1 )
    var shade : TextureRect = TextureRect . new ( )
    shade . texture = fade
    shade . set_meta ( "race_theme_gradient" , true )
    shade . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    shade . mouse_filter = Control . MOUSE_FILTER_IGNORE
    panel . add_child ( shade )
    return panel


func _art_caption ( panel : Control ) -> VBoxContainer :
    var margin : MarginContainer = MarginContainer . new ( )
    margin . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    for side : String in [ "left" , "right" , "top" , "bottom" ] :
        margin . add_theme_constant_override ( "margin_" + side , 18 )
    margin . mouse_filter = Control . MOUSE_FILTER_PASS
    panel . add_child ( margin )
    var stack : VBoxContainer = VBoxContainer . new ( )
    stack . alignment = BoxContainer . ALIGNMENT_END
    stack . add_theme_constant_override ( "separation" , 4 )
    margin . add_child ( stack )
    return stack


var planet_status
var beginner_guide


func _ready ( ) -> void :
    report_notifications = ReportNotificationsScript.new()
    report_notifications.setup(self)
    add_child(report_notifications)
    interaction_guard = InteractionGuardScript . new ( )
    interaction_guard . name = "InputRefreshGuard"
    add_child ( interaction_guard )
    _load_ui_preferences ( )
    RaceTheme . set_race ( "" )
    theme = _make_theme ( )
    var background : ColorRect = ColorRect . new ( )
    background . color = _ui_color ( Color ( "08110d" ) )
    background . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    background . mouse_filter = Control . MOUSE_FILTER_IGNORE
    add_child ( background )
    _make_login ( )
    review_prompt = ReviewPromptScript . new ( )
    review_prompt . setup ( self )
    megastructure_ui = MegastructureUIScript . new ( )
    megastructure_ui . setup ( self )
    _make_app ( )
    _make_update_overlay ( )
    compact_ui = CompactUIScript . new ( )
    compact_ui . setup ( self )
    planetary_ui = PlanetaryUIScript . new ( )
    planetary_ui . setup ( self )
    fleet_navigation = FleetNavigationScript . new ( )
    fleet_navigation . setup ( self )
    project_ui = preload ( "res://client/scripts/project_ui.gd" ) . new ( )
    project_ui . setup ( self )
    planned_queue_ui = PlannedQueueUIScript . new ( )
    planned_queue_ui . setup ( self )
    planet_status = PlanetStatusScript . new ( )
    planet_status . setup ( self )
    beginner_guide = BeginnerGuideScript . new ( )
    beginner_guide . setup ( self , tab_bodies [ 0 ] )
    communications = CommunicationsScript . new ( )
    add_child ( communications )
    communications . setup ( self )
    alliance_ui = AllianceUIScript . new ( )
    add_child ( alliance_ui )
    alliance_ui . setup ( self )
    ranking_ui = RankingUIScript.new()
    add_child(ranking_ui)
    ranking_ui.setup(self)
    empire_name_ui = preload("res://client/scripts/empire_name_ui.gd").new()
    add_child(empire_name_ui)
    empire_name_ui.setup(self)
    PlayUpdates.changed.connect(_sync_play_update)

    RaceTheme . apply_tree ( self )
    _create_command_request ( )
    google_login = GoogleLoginScript . new ( )
    google_login . setup ( self )
    google_login . configuration_changed . connect ( _on_google_configuration )
    google_login . changed . connect ( _refresh_google_controls )
    google_login . needs_name . connect ( _on_google_name_needed )
    google_login . completed . connect ( _on_google_completed )
    google_login . failed . connect ( _on_google_failed )
    google_login . cancelled . connect ( _on_google_cancelled )
    email_login = EmailLoginScript . new ( )
    email_login . setup ( self )
    email_login . configuration_changed . connect ( _refresh_email_controls )
    email_login . changed . connect ( _refresh_email_controls )
    email_login . needs_name . connect ( _on_email_name_needed )
    email_login . completed . connect ( _on_email_completed )
    email_login . failed . connect ( _on_email_failed )
    queue_billing = QueueBillingScript . new ( )
    queue_billing . setup ( self )
    queue_billing . changed . connect ( planned_queue_ui . refresh_offer )
    poll_timer = Timer . new ( )
    poll_timer . wait_time = 3.0
    poll_timer . timeout . connect ( _poll )
    add_child ( poll_timer )
    poll_timer . start ( )
    update_timer = Timer . new ( )
    update_timer . wait_time = 60.0
    update_timer . timeout . connect ( _check_client_version )
    add_child ( update_timer )
    update_timer . start ( )
    _load_session ( )
    if has_meta ( "language_resume" ) :
        language_resume = get_meta ( "language_resume" )
        remove_meta ( "language_resume" )
        requested_planet = str ( language_resume . get ( "planet" , "" ) )
        selected_system = str ( language_resume . get ( "system" , "" ) )
        selected_target = str ( language_resume . get ( "target" , "" ) )
        selected_scout_system = str ( language_resume . get ( "scout_system" , "" ) )
        name_field . text = str ( language_resume . get ( "name" , name_field . text ) )
        _set_login_mode ( str ( language_resume . get ( "login_mode" , "" ) ) , false )
        password_field . text = str ( language_resume . get ( "password" , "" ) )
        repeat_password_field . text = str ( language_resume . get ( "repeat_password" , "" ) )
        language_resume . erase ( "password" )
        language_resume . erase ( "repeat_password" )
    _set_field_text ( server_field , server_url )
    connection_setup . visible = false
    _refresh_connection_hint ( )
    if session_token . is_empty ( ) :
        _show_login ( server_config_error , not server_config_error . is_empty ( ) )
    else :
        _show_login ( I18n . t ( "Przywracanie połączenia z imperium…" ) )
        _poll ( )
    _check_client_version ( )
    google_login . load_configuration ( )
    email_login . load_configuration ( )


func _notification ( what : int ) -> void :
    if what in [ NOTIFICATION_APPLICATION_PAUSED , NOTIFICATION_APPLICATION_FOCUS_OUT ] :
        player_activity . set_foreground ( false )
    elif what in [ NOTIFICATION_APPLICATION_RESUMED , NOTIFICATION_APPLICATION_FOCUS_IN ] :
        player_activity . set_foreground ( true )
        if is_node_ready ( ) :
            _poll . call_deferred ( )
            if showing_login and login_announcement != null :
                login_announcement . load_from_server ( true )
    if what == NOTIFICATION_WM_GO_BACK_REQUEST and review_prompt != null and review_prompt.is_visible():
        review_prompt._later()
        return
    if what == NOTIFICATION_WM_GO_BACK_REQUEST :
        # A choice list owns this Back. Its deferred close must not also
        # navigate the destination map underneath in the same notification.
        if MobileChoiceScript . _back_guard_count > 0 :
            return
        var subscription_prompt = get_node_or_null ( "SubscriptionMilestonePrompt" )
        if subscription_prompt != null and subscription_prompt . handle_back ( ) :
            return
    if what == NOTIFICATION_WM_GO_BACK_REQUEST and ranking_ui != null and ranking_ui.visible :
        ranking_ui.close()
        return
    if what == NOTIFICATION_WM_GO_BACK_REQUEST and alliance_ui != null and alliance_ui . visible :
        alliance_ui . go_back ( )
        return
    if what == NOTIFICATION_WM_GO_BACK_REQUEST and communications != null and communications . visible :
        communications . go_back ( )
        return
    if what == NOTIFICATION_WM_GO_BACK_REQUEST and compact_ui != null and compact_ui . details_open ( ) :
        compact_ui . go_back ( )
        return
    if what == NOTIFICATION_WM_GO_BACK_REQUEST and release_open :
        if not is_instance_valid ( update_overlay ) or not update_overlay . visible :
            _close_release_panel ( )
        return
    if what == NOTIFICATION_WM_GO_BACK_REQUEST and skill_open :
        if not is_instance_valid ( update_overlay ) or not update_overlay . visible :
            _close_skill_wheel ( )
    if what in [ NOTIFICATION_APPLICATION_RESUMED , NOTIFICATION_APPLICATION_FOCUS_IN ] and is_node_ready ( ) :
        _check_client_version . call_deferred ( )


func _input ( event : InputEvent ) -> void :
    if review_prompt != null and review_prompt.is_visible():
        if event.is_action_pressed("ui_cancel"):
            get_viewport().set_input_as_handled()
            review_prompt._later()
        return
    player_activity . observe_input ( event , is_instance_valid ( interaction_guard ) and interaction_guard . _recovering )
    if event.is_action_pressed("ui_cancel") and MobileChoiceScript._back_guard_count == 0 and ranking_ui != null and ranking_ui.visible :
        ranking_ui.close()
        get_viewport().set_input_as_handled()
        return
    if event . is_action_pressed ( "ui_cancel" ) and MobileChoiceScript . _back_guard_count == 0 and compact_ui != null and compact_ui . details_open ( ) :
        compact_ui . go_back ( )
        get_viewport ( ) . set_input_as_handled ( )


func _process ( delta : float ) -> void :
    if fleet_navigation != null :
        fleet_navigation . tick ( )
    if _finish_response_jobs():
        return
    _flush_deferred_state ( )
    if not pending_language . is_empty ( ) and _language_change_safe ( ) :
        _apply_language_change . call_deferred ( )
    clock_accumulator += delta
    if clock_accumulator < 0.3 :
        return
    clock_accumulator = 0.0
    _update_mobile_margins ( )
    if not state . is_empty ( ) :
        _update_clock ( )


func _update_mobile_margins ( ) -> void :
    if OS . get_name ( ) != "Android" :
        return
    var window_height : int = DisplayServer . window_get_size ( ) . y
    var keyboard_height : int = DisplayServer . virtual_keyboard_get_height ( )
    if keyboard_height == 0 :
        keyboard_baseline_height = window_height
    var already_resized : int = maxi ( 0 , keyboard_baseline_height - window_height )
    var keyboard_overlap : int = maxi ( 0 , keyboard_height - already_resized )
    var inverse : Transform2D = get_viewport ( ) . get_screen_transform ( ) . affine_inverse ( )
    var safe : Rect2i = DisplayServer . get_display_safe_area ( )
    var safe_start : Vector2 = inverse * Vector2 ( safe . position )
    var safe_end : Vector2 = inverse * Vector2 ( safe . end )
    var left : int = maxi ( 22 , ceili ( safe_start . x ) )
    var top : int = maxi ( 22 , ceili ( safe_start . y ) )
    var right : int = maxi ( 22 , ceili ( size . x - safe_end . x ) )
    var bottom : int = maxi ( 22 , ceili ( maxf ( size . y - safe_end . y , float ( keyboard_overlap ) * inverse . y . length ( ) ) ) )
    var next_insets : Vector4i = Vector4i ( left , top , right , bottom )
    if next_insets == mobile_insets :
        return
    mobile_insets = next_insets
    for margin : MarginContainer in [ login_margin , app_screen , update_margin , race_screen , skill_margin , release_panel , communications . margin if communications != null else null , alliance_ui . margin if alliance_ui != null else null , compact_ui . modal_margin if compact_ui != null else null , ranking_ui.margin if ranking_ui != null else null ] :
        if not is_instance_valid ( margin ) :
            continue
        margin . add_theme_constant_override ( "margin_left" , left )
        margin . add_theme_constant_override ( "margin_top" , top )
        margin . add_theme_constant_override ( "margin_right" , right )
        margin . add_theme_constant_override ( "margin_bottom" , bottom )
    var focused : Control = get_viewport ( ) . gui_get_focus_owner ( )
    if focused != null :
        var ancestor : Node = focused . get_parent ( )
        while ancestor != null :
            if ancestor is ScrollContainer :
                ancestor . call_deferred ( "ensure_control_visible" , focused )
                break
            ancestor = ancestor . get_parent ( )


func _ui_color ( value : Color ) -> Color :
    return RaceTheme . color ( value )


func _apply_race_palette ( race_id : String ) -> void :
    if RaceTheme . set_race ( race_id ) :
        RaceTheme . apply_tree ( self )
        if is_instance_valid ( skill_wheel ) :
            skill_wheel . queue_redraw ( )
    if is_instance_valid ( galaxy_map ) :
        galaxy_map . call ( "set_race_palette" , RaceTheme . palette ( ) )


func _make_theme ( ) -> Theme :
    var result : Theme = Theme . new ( )
    result . default_font_size = 26
    result . set_color ( "font_color" , "Label" , _ui_color ( Color ( "e7eee4" ) ) )
    result . set_color ( "font_color" , "Button" , _ui_color ( Color ( "e2ecdf" ) ) )
    result . set_color ( "font_disabled_color" , "Button" , _ui_color ( Color ( "7f9384" ) ) )
    result . set_color ( "font_color" , "LineEdit" , _ui_color ( Color ( "e7eee4" ) ) )
    result . set_color ( "font_placeholder_color" , "LineEdit" , _ui_color ( Color ( "8caa94" ) ) )
    result . set_color ( "caret_color" , "LineEdit" , _ui_color ( Color ( "91c89b" ) ) )
    result . set_color ( "selection_color" , "LineEdit" , _ui_color ( Color ( "3b6047" ) ) )
    result . set_color ( "font_selected_color" , "LineEdit" , _ui_color ( Color ( "edf3e9" ) ) )
    result . set_stylebox ( "normal" , "Button" , _style ( "000000" , "39553f" , 13 , 15 ) )
    result . set_stylebox ( "hover" , "Button" , _style ( "284633" , "91c89b" , 13 , 15 ) )
    result . set_stylebox ( "pressed" , "Button" , _style ( "2c5139" , "91c89b" , 13 , 15 ) )
    result . set_stylebox ( "disabled" , "Button" , _style ( "151515" , "262626" , 13 , 15 ) )
    result . set_stylebox ( "focus" , "Button" , _focus_style ( ) )
    for kind : String in [ "normal" , "hover" , "pressed" , "disabled" , "focus" ] :
        result . set_stylebox ( kind , "OptionButton" , result . get_stylebox ( kind , "Button" ) )
    result . set_color ( "font_color" , "OptionButton" , _ui_color ( Color ( "e7eee4" ) ) )
    result . set_color ( "font_disabled_color" , "OptionButton" , _ui_color ( Color ( "7f9384" ) ) )
    result . set_stylebox ( "normal" , "LineEdit" , _style ( "151515" , "262626" , 12 , 14 ) )
    result . set_stylebox ( "focus" , "LineEdit" , _style ( "11291b" , "91c89b" , 12 , 14 ) )
    result . set_stylebox ( "panel" , "PopupMenu" , _style ( "151515" , "45654c" , 12 , 12 ) )
    result . set_constant ( "v_separation" , "PopupMenu" , 56 )
    result . set_color ( "font_color" , "PopupMenu" , _ui_color ( Color ( "edf3e9" ) ) )
    result . set_color ( "font_hover_color" , "PopupMenu" , _ui_color ( Color ( "edf3e9" ) ) )
    result . set_stylebox ( "hover" , "PopupMenu" , _style ( "2c5139" , "45654c" , 8 , 8 ) )
    for scrollbar : String in [ "VScrollBar" , "HScrollBar" ] :
        result . set_stylebox ( "scroll" , scrollbar , _style ( "0a1710" , "0a1710" , 4 , 4 ) )
        result . set_stylebox ( "grabber" , scrollbar , _style ( "45654c" , "45654c" , 4 , 4 ) )
        result . set_stylebox ( "grabber_highlight" , scrollbar , _style ( "66896d" , "66896d" , 4 , 4 ) )
        result . set_stylebox ( "grabber_pressed" , scrollbar , _style ( "91c89b" , "91c89b" , 4 , 4 ) )
    result . set_constant ( "separation" , "VBoxContainer" , 14 )
    result . set_constant ( "separation" , "HBoxContainer" , 12 )
    return result


func _style ( background : String , border : String , radius : int = 18 , padding : int = 18 ) -> StyleBoxFlat :
    var box : StyleBoxFlat = StyleBoxFlat . new ( )
    box . bg_color = _ui_color ( Color ( background ) )
    box . border_color = _ui_color ( Color ( border ) )
    box . set_border_width_all ( 1 )
    box . set_corner_radius_all ( radius )
    box . content_margin_left = padding
    box . content_margin_right = padding
    box . content_margin_top = padding
    box . content_margin_bottom = padding
    return box


func _focus_style ( ) -> StyleBoxFlat :
    var box : StyleBoxFlat = _style ( "00000000" , "91c89b" , 13 , 0 )
    box . set_border_width_all ( 2 )
    return box


func _label ( text_value : String , font_size : int = 22 , color : String = "e7eee4" ) -> Label :
    var node : Label = Label . new ( )
    node . text = text_value
    node . add_theme_font_size_override ( "font_size" , maxi ( 22 , font_size ) )
    node . add_theme_color_override ( "font_color" , _ui_color ( Color ( color ) ) )
    node . autowrap_mode = TextServer . AUTOWRAP_WORD_SMART
    node . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    node . mouse_filter = Control . MOUSE_FILTER_IGNORE
    return node


func _token_label ( text_value : String , font_size : int = 22 , color : String = "e7eee4" ) -> Label :


    var node : Label = _label ( text_value , font_size , color )
    node . autowrap_mode = TextServer . AUTOWRAP_OFF
    node . size_flags_horizontal = Control . SIZE_SHRINK_BEGIN
    node . size_flags_vertical = Control . SIZE_SHRINK_CENTER
    return node


func _button ( text_value : String , callback : Callable , primary : bool = false ) -> Button :
    var node : Button = Button . new ( )
    node . action_mode = BaseButton . ACTION_MODE_BUTTON_RELEASE
    node . mouse_filter = Control . MOUSE_FILTER_PASS
    node . text = text_value
    node . autowrap_mode = TextServer . AUTOWRAP_WORD_SMART
    node . clip_text = true
    node . tooltip_text = text_value
    node . custom_minimum_size . y = 76
    node . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    node . pressed . connect ( callback )
    if primary :
        node . add_theme_stylebox_override ( "normal" , _style ( "2b4f36" , "91c89b" , 13 , 15 ) )
        node . add_theme_color_override ( "font_color" , _ui_color ( Color ( "d4ebd6" ) ) )
    return node


func _choice ( title : String , height : float = 80.0 ) -> MobileChoiceScript :


    var node : MobileChoiceScript = MobileChoiceScript . new ( )
    node . dialog_title = title
    node . custom_minimum_size . y = height
    node . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    node . text_overrun_behavior = TextServer . OVERRUN_TRIM_ELLIPSIS
    return node


func _load_ui_preferences ( ) -> void :
    detailed_descriptions = UIPreferencesScript . load_detailed_descriptions ( interface_settings_path )
    research_three_rows = UIPreferencesScript . load_research_three_rows ( interface_settings_path )


func _add_description_setting ( parent : Node ) -> void :
    detailed_descriptions_button = CheckButton . new ( )
    detailed_descriptions_button . name = "DetailedDescriptionsSetting"
    detailed_descriptions_button . text = I18n . t ( "Szczegółowe opisy" )
    detailed_descriptions_button . tooltip_text = I18n . t ( "Dodatkowe objaśnienia, przykłady i progi odblokowania." )
    detailed_descriptions_button . custom_minimum_size . y = 64
    detailed_descriptions_button . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    detailed_descriptions_button . alignment = HORIZONTAL_ALIGNMENT_LEFT
    detailed_descriptions_button . autowrap_mode = TextServer . AUTOWRAP_WORD_SMART
    detailed_descriptions_button . set_pressed_no_signal ( detailed_descriptions )
    detailed_descriptions_button . toggled . connect ( _on_detailed_descriptions_toggled )
    parent . add_child ( detailed_descriptions_button )


func _on_detailed_descriptions_toggled ( enabled : bool ) -> void :
    if enabled == detailed_descriptions :
        return
    if UIPreferencesScript . save_detailed_descriptions ( enabled , interface_settings_path ) != OK :
        detailed_descriptions_button . set_pressed_no_signal ( detailed_descriptions )
        _notify ( I18n . t ( "Nie udało się zapisać ustawienia opisów." ) , true )
        return
    detailed_descriptions = enabled
    if compact_ui != null :
        compact_ui . refresh_description_mode ( )


func _add_language_picker ( parent : Node ) -> void :
    var picker : MobileChoiceScript = _choice ( I18n . t ( "Język / Language" ) , 72 )
    picker . name = "LanguagePicker"
    picker . tooltip_text = I18n . t ( "Język" )
    for caption : String in I18n . LANGUAGE_NAMES :
        picker . add_item ( caption )
    picker . select ( I18n . LOCALES . find ( I18n . locale ) )
    picker . item_selected . connect ( func ( index : int ) -> void :
        if index < 0 or index >= I18n . LOCALES . size ( ) :
            return
        pending_language = I18n . LOCALES [ index ] if I18n . LOCALES [ index ] != I18n . locale else ""
        if not pending_language . is_empty ( ) :
            if _language_change_safe ( ) :
                _apply_language_change . call_deferred ( )
            else :
                _notify ( I18n . t ( "Język zostanie zmieniony po zakończeniu bieżącej operacji." ) )
    )
    parent . add_child ( picker )


func _language_change_safe ( ) -> bool :
    return ( google_login == null or not google_login . is_active ( ) ) and ( email_login == null or not email_login . is_active ( ) ) and not _ui_interacting ( ) and not request_pending and uncertain_action . is_empty ( ) and not update_request_pending and ( alliance_ui == null or ( not alliance_ui . action_busy and alliance_ui . retry_context . is_empty ( ) ) )


func _apply_language_change ( ) -> void :
    if pending_language . is_empty ( ) or not _language_change_safe ( ) :
        return
    var next_language : String = pending_language
    pending_language = ""
    if not I18n . set_locale ( next_language ) :
        _notify ( I18n . t ( "Nie udało się zapisać języka. Spróbuj ponownie." ) , true )
        return
    _cancel_state_request ( )


    var resume : Dictionary = {
        "planet" : selected_planet , "system" : selected_system , "target" : selected_target , "scout_system" : selected_scout_system ,
        "tab" : current_tab , "fleet_mode" : fleet_mode , "name" : name_field . text ,
        "password" : password_field . text , "repeat_password" : repeat_password_field . text ,
        "login_mode" : login_mode , "settings" : options_panel . get_parent ( ) . visible ,
        "ships" : { } , "cargo" : { } , "mission" : mission_picker . selected ,
        "map" : galaxy_overview . visible ,
        "biome" : biome_expanded , "composing" : compact_ui . composing if compact_ui != null else false ,
    }
    for key : String in fleet_inputs :
        fleet_inputs [ key ] . apply ( )
        resume [ "ships" ] [ key ] = fleet_inputs [ key ] . value
    for key : String in cargo_inputs :
        cargo_inputs [ key ] . apply ( )
        resume [ "cargo" ] [ key ] = cargo_inputs [ key ] . value
    poll_timer . stop ( )
    update_timer . stop ( )
    DisplayServer . virtual_keyboard_hide ( )
    var replacement : Control = _new_language_client ( )
    replacement . set_meta ( "language_resume" , resume )
    var parent : Node = get_parent ( )
    var was_current : bool = get_tree ( ) . current_scene == self
    parent . add_child ( replacement )
    if was_current :
        get_tree ( ) . current_scene = replacement
    parent . remove_child ( self )
    queue_free ( )


func _new_language_client ( ) -> Control :
    var scene : PackedScene = load ( "res://client/scenes/main.tscn" )
    return scene . instantiate ( )


func _restore_language_view ( ) -> void :
    if language_resume . is_empty ( ) :
        return
    var resume : Dictionary = language_resume
    language_resume = { }
    _open_tab ( clampi ( int ( resume . get ( "tab" , 0 ) ) , 0 , 4 ) )
    _set_fleet_mode ( int ( resume . get ( "fleet_mode" , 0 ) ) )
    if compact_ui != null :
        compact_ui . composing = bool ( resume . get ( "composing" , false ) )
    options_panel . get_parent ( ) . visible = bool ( resume . get ( "settings" , false ) )
    galaxy_overview . visible = bool ( resume . get ( "map" , true ) )
    galaxy_toggle . text = I18n . t ( "Układ" ) if galaxy_overview . visible else I18n . t ( "Mapa" )
    biome_expanded = bool ( resume . get ( "biome" , false ) )
    biome_toggle . text = I18n . t ( "Ukryj krajobraz" ) if biome_expanded else I18n . t ( "Krajobraz planety" )
    colony_panorama . visible = biome_expanded or str ( state . get ( "player" , { } ) . get ( "race_id" , "" ) ) . is_empty ( )
    mission_picker . select ( clampi ( int ( resume . get ( "mission" , 0 ) ) , 0 , mission_picker . item_count - 1 ) )
    for key : String in resume . get ( "ships" , { } ) :
        if fleet_inputs . has ( key ) :
            fleet_inputs [ key ] . value = resume [ "ships" ] [ key ]
    for key : String in resume . get ( "cargo" , { } ) :
        if cargo_inputs . has ( key ) :
            cargo_inputs [ key ] . value = resume [ "cargo" ] [ key ]
    _update_mission_hint ( )
    _invalidate_quote ( )


func _card ( parent : Node ) -> VBoxContainer :
    var panel : PanelContainer = PanelContainer . new ( )
    panel . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    panel . mouse_filter = Control . MOUSE_FILTER_PASS
    panel . add_theme_stylebox_override ( "panel" , _style ( "101010" , "262626" , 20 , 20 ) )
    parent . add_child ( panel )
    var body : VBoxContainer = VBoxContainer . new ( )
    panel . add_child ( body )
    return body


func _texture ( key : String ) -> Texture2D :
    return RaceTheme . icon_texture ( key )


func _icon ( key : String , pixels : int = 32 ) -> TextureRect :
    var art : TextureRect = TextureRect . new ( )
    art . texture = _texture ( key )
    art . custom_minimum_size = Vector2 ( pixels , pixels )
    art . expand_mode = TextureRect . EXPAND_IGNORE_SIZE
    art . stretch_mode = TextureRect . STRETCH_KEEP_ASPECT_CENTERED
    art . size_flags_vertical = Control . SIZE_SHRINK_CENTER
    art . mouse_filter = Control . MOUSE_FILTER_IGNORE
    return art


func _brand_icon ( pixels : int ) -> TextureRect :
    var art : TextureRect = TextureRect . new ( )
    var icon_texture : Texture2D = load ( BRAND_ICON_PATH ) as Texture2D
    art . texture = icon_texture
    art . custom_minimum_size = Vector2 ( pixels , pixels )
    art . expand_mode = TextureRect . EXPAND_IGNORE_SIZE
    art . stretch_mode = TextureRect . STRETCH_KEEP_ASPECT_CENTERED
    art . size_flags_horizontal = Control . SIZE_SHRINK_CENTER
    art . size_flags_vertical = Control . SIZE_SHRINK_CENTER
    art . mouse_filter = Control . MOUSE_FILTER_IGNORE
    return art


func _meter ( tint : String ) -> ProgressBar :
    var bar : ProgressBar = ProgressBar . new ( )
    bar . custom_minimum_size . y = 10
    bar . show_percentage = false
    bar . mouse_filter = Control . MOUSE_FILTER_IGNORE
    bar . add_theme_stylebox_override ( "background" , _style ( "0a1710" , "0a1710" , 5 , 0 ) )
    bar . add_theme_stylebox_override ( "fill" , _style ( tint , tint , 5 , 0 ) )
    return bar


func _details ( parent : Node , content : Control ) -> void :
    content . visible = false
    var toggle : Button = _button ( I18n . t ( "Szczegóły" ) , func ( ) -> void : content . visible = not content . visible )
    toggle . custom_minimum_size . y = 62
    toggle . add_theme_font_size_override ( "font_size" , 22 )
    parent . add_child ( toggle )
    parent . add_child ( content )


func _cost_icons ( parent : Node ) -> Dictionary :
    var flow : HFlowContainer = HFlowContainer . new ( )
    flow . mouse_filter = Control . MOUSE_FILTER_PASS
    flow . add_theme_constant_override ( "h_separation" , 20 )
    parent . add_child ( flow )
    var controls : Dictionary = { }
    for key : String in RESOURCE_KEYS :
        var item : HBoxContainer = _row ( flow )
        item . size_flags_horizontal = Control . SIZE_SHRINK_BEGIN
        item . add_theme_constant_override ( "separation" , 5 )
        item . add_child ( _icon ( key , 26 ) )
        var amount : Label = _token_label ( "0" , 22 )
        item . add_child ( amount )
        controls [ key ] = { "row" : item , "amount" : amount }
    return controls


func _row ( parent : Node ) -> HBoxContainer :
    var row : HBoxContainer = HBoxContainer . new ( )
    row . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    parent . add_child ( row )
    return row


func _margin ( ) -> MarginContainer :
    var node : MarginContainer = MarginContainer . new ( )
    node . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    for side : String in [ "left" , "right" , "top" , "bottom" ] :
        node . add_theme_constant_override ( "margin_" + side , 22 )
    add_child ( node )
    return node


func _field ( parent : Node , caption : String , placeholder : String , secret : bool = false ) -> LineEdit :
    parent . add_child ( _label ( caption , 19 , "a0b3a4" ) )
    var field : LineEdit = LineEdit . new ( )
    field . placeholder_text = placeholder
    field . custom_minimum_size . y = 88
    field . secret = secret
    field . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    parent . add_child ( field )
    return field


func _login_card_style ( ) -> StyleBoxFlat :
    var box : StyleBoxFlat = StyleBoxFlat . new ( )
    box . bg_color = Color ( 0.012 , 0.031 , 0.056 , 0.97 )
    box . border_color = Color ( "388fbf" )
    box . set_border_width_all ( 2 )
    box . set_corner_radius_all ( 24 )
    box . set_content_margin_all ( 24.0 )
    box . shadow_color = Color ( 0.06 , 0.42 , 0.75 , 0.3 )
    box . shadow_size = 13
    return box


func _login_style_button ( button : Button , highlighted : bool ) -> void :
    var normal : StyleBoxFlat = _style ( "08243b" if highlighted else "061726" , "f0b867" if highlighted else "4bbfed" , 14 , 17 )
    normal . set_border_width_all ( 2 )
    normal . shadow_color = Color ( "ebaf64" , 0.22 ) if highlighted else Color ( "2c9ddd" , 0.26 )
    normal . shadow_size = 6
    var hovered : StyleBoxFlat = normal . duplicate ( )
    hovered . bg_color = Color ( "17445f" ) if highlighted else Color ( "11466a" )
    hovered . set_border_width_all ( 3 )
    hovered . shadow_size = 10
    var pressed : StyleBoxFlat = normal . duplicate ( )
    pressed . bg_color = Color ( "293848" ) if highlighted else Color ( "0a527c" )
    button . add_theme_stylebox_override ( "normal" , normal )
    button . add_theme_stylebox_override ( "hover" , hovered )
    button . add_theme_stylebox_override ( "pressed" , pressed )
    button . add_theme_stylebox_override ( "focus" , _focus_style ( ) )
    button . add_theme_color_override ( "font_color" , Color ( "ffe4b6" ) if highlighted else Color ( "ecf8ff" ) )
    button . add_theme_font_size_override ( "font_size" , 25 )
    button . custom_minimum_size . y = 91
    button . alignment = HORIZONTAL_ALIGNMENT_CENTER


func _make_login ( ) -> void :
    login_screen = Control . new ( )
    login_screen . name = "LoginScreen"
    login_screen . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    add_child ( login_screen )
    var backdrop : TextureRect = TextureRect . new ( )
    backdrop . name = "LoginPortraitBackground"
    backdrop . texture = load ( LOGIN_BACKGROUND_PATH ) as Texture2D
    backdrop . expand_mode = TextureRect . EXPAND_IGNORE_SIZE
    backdrop . stretch_mode = TextureRect . STRETCH_KEEP_ASPECT_CENTERED
    backdrop . mouse_filter = Control . MOUSE_FILTER_IGNORE
    backdrop . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    login_screen . add_child ( backdrop )


    var gradient : Gradient = Gradient . new ( )
    gradient . offsets = PackedFloat32Array ( [ 0.0 , 0.4 , 0.58 , 0.78 , 1.0 ] )
    gradient . colors = PackedColorArray ( [ Color ( 0.01 , 0.017 , 0.033 , 0.0 ) , Color ( 0.01 , 0.017 , 0.033 , 0.0 ) , Color ( 0.01 , 0.017 , 0.033 , 0.4 ) , Color ( 0.01 , 0.017 , 0.033 , 0.88 ) , Color ( 0.01 , 0.017 , 0.033 , 0.98 ) ] )
    var gradient_texture : GradientTexture2D = GradientTexture2D . new ( )
    gradient_texture . gradient = gradient
    gradient_texture . width = 1
    gradient_texture . height = 256
    gradient_texture . fill_from = Vector2 ( 0.0 , 0.0 )
    gradient_texture . fill_to = Vector2 ( 0.0 , 1.0 )
    var shade : TextureRect = TextureRect . new ( )
    shade . name = "LoginReadabilityShade"
    shade . texture = gradient_texture
    shade . expand_mode = TextureRect . EXPAND_IGNORE_SIZE
    shade . mouse_filter = Control . MOUSE_FILTER_IGNORE
    shade . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    login_screen . add_child ( shade )
    login_name_background = ColorRect . new ( )
    login_name_background . name = "EmpireNameBackground"
    login_name_background . color = Color ( "030b16" )
    login_name_background . mouse_filter = Control . MOUSE_FILTER_IGNORE
    login_name_background . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    login_name_background . visible = false
    login_screen . add_child ( login_name_background )

    login_margin = MarginContainer . new ( )
    login_margin . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    for side : String in [ "left" , "right" , "top" , "bottom" ] :
        login_margin . add_theme_constant_override ( "margin_" + side , 22 )
    login_screen . add_child ( login_margin )
    login_scroll = TouchScrollScript . new ( )
    login_scroll . horizontal_scroll_mode = ScrollContainer . SCROLL_MODE_DISABLED
    login_scroll . follow_focus = true
    login_margin . add_child ( login_scroll )
    var stack : VBoxContainer = VBoxContainer . new ( )
    stack . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    stack . add_theme_constant_override ( "separation" , 16 )
    login_scroll . add_child ( stack )
    var name_card : VBoxContainer = _card ( stack )
    name_card . add_theme_constant_override ( "separation" , 12 )
    login_name_panel = name_card . get_parent ( ) as PanelContainer
    login_name_panel . name = "EmpireNamePanel"
    login_name_panel . add_theme_stylebox_override ( "panel" , _login_card_style ( ) )
    login_name_panel . visible = false


    login_hero_spacer = Control . new ( )
    login_hero_spacer . name = "LoginArtworkSpace"
    login_hero_spacer . mouse_filter = Control . MOUSE_FILTER_IGNORE
    stack . add_child ( login_hero_spacer )
    login_scroll . resized . connect ( _update_login_art_layout )
    _update_login_art_layout . call_deferred ( )
    login_announcement = LoginAnnouncementScript . new ( )
    login_announcement . setup ( self , stack )
    var card : VBoxContainer = _card ( stack )
    card . add_theme_constant_override ( "separation" , 14 )
    var login_card : PanelContainer = card . get_parent ( ) as PanelContainer
    login_card . name = "LoginActionPanel"
    login_choice_panel = login_card
    login_card . add_theme_stylebox_override ( "panel" , _login_card_style ( ) )
    var small_brand : Label = _label ( "✦  ALIEN COLONIES  ✦" , 21 , "7ddcf2" )
    small_brand . horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    card . add_child ( small_brand )
    var invitation : Label = _label ( I18n . t ( "Zaloguj się lub stwórz nowe imperium." ) , 26 )
    invitation . horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    card . add_child ( invitation )
    google_login_button = _button ( I18n . t ( "Kontynuuj z Google" ) , _start_google_login , true )
    google_login_button . name = "GoogleLoginButton"
    google_login_button . icon = load ( "res://client/assets/google_signin_g.png" ) as Texture2D
    google_login_button . icon_alignment = HORIZONTAL_ALIGNMENT_LEFT
    google_login_button . expand_icon = true
    google_login_button . add_theme_constant_override ( "icon_max_width" , 38 )
    _login_style_button ( google_login_button , false )
    google_login_button . disabled = true
    card . add_child ( google_login_button )
    create_account_button = _button ( I18n . t ( "Utwórz konto" ) , _create_account_from_login , true )
    create_account_button . name = "CreateAccountButton"
    create_account_button . tooltip_text = I18n . t ( "Nowe imperium utworzysz po potwierdzeniu konta Google lub e-mail." )
    _login_style_button ( create_account_button , true )
    create_account_button . disabled = true
    card . add_child ( create_account_button )
    email_login_button = _button ( I18n . t ( "Kontynuuj przez e-mail" ) , _open_email_login )
    email_login_button . name = "EmailLoginButton"
    _login_style_button ( email_login_button , false )
    email_login_button . visible = false
    card . add_child ( email_login_button )
    email_form = VBoxContainer . new ( )
    email_form . name = "EmailLoginForm"
    email_form . add_theme_constant_override ( "separation" , 12 )
    email_form . visible = false
    card . add_child ( email_form )
    email_form . add_child ( _label ( I18n . t ( "Wyślemy jednorazowy link do logowania. Hasło nie jest potrzebne." ) , 21 , "a0b3a4" ) )
    var email_address_row : VBoxContainer = VBoxContainer . new ( )
    email_form . add_child ( email_address_row )
    email_field = _field ( email_address_row , I18n . t ( "ADRES E-MAIL" ) , "name@example.com" )
    email_field . name = "EmailAddress"
    email_field . max_length = 254
    email_field . virtual_keyboard_type = LineEdit . KEYBOARD_TYPE_EMAIL_ADDRESS
    email_field . text_submitted . connect ( func ( _text : String ) -> void : _send_email_login ( ) )
    email_send_button = _button ( I18n . t ( "Wyślij link do logowania" ) , _send_email_login , true )
    email_send_button . name = "SendEmailLoginLink"
    email_form . add_child ( email_send_button )
    email_wait_label = _label ( "" , 21 , "a0b3a4" )
    email_wait_label . name = "EmailLoginStatus"
    email_form . add_child ( email_wait_label )
    email_resend_button = _button ( I18n . t ( "Wyślij link ponownie" ) , _resend_email_login )
    email_resend_button . name = "ResendEmailLoginLink"
    email_form . add_child ( email_resend_button )
    email_cancel_button = _button ( I18n . t ( "Anuluj logowanie e-mail" ) , _cancel_email_login )
    email_cancel_button . name = "CancelEmailLogin"
    email_form . add_child ( email_cancel_button )
    _add_language_picker ( card )
    var language_picker : Control = card . get_node ( "LanguagePicker" ) as Control
    language_picker . custom_minimum_size . y = 56
    language_picker . add_theme_font_size_override ( "font_size" , 22 )
    login_notice = PanelContainer . new ( )
    login_notice . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    login_notice . focus_mode = Control . FOCUS_ALL
    login_notice . visible = false
    card . add_child ( login_notice )
    var notice_body : VBoxContainer = VBoxContainer . new ( )
    login_notice . add_child ( notice_body )
    login_message_title = _label ( "" , 24 , "ffb4aa" )
    notice_body . add_child ( login_message_title )
    login_message = _label ( "" , 23 )
    notice_body . add_child ( login_message )
    login_form = VBoxContainer . new ( )
    login_form . add_theme_constant_override ( "separation" , 12 )
    login_form . name = "EmpireNameForm"
    name_card . add_child ( login_form )
    login_form_title = _label ( "" , 28 )
    login_form . add_child ( login_form_title )
    login_form_hint = _label ( "" , 20 , "a8bcac" )
    login_form . add_child ( login_form_hint )
    name_field = _field ( login_form , I18n . t ( "NAZWA IMPERIUM" ) , "" )
    name_field . name = "EmpireName"
    login_password_row = VBoxContainer . new ( )
    login_form . add_child ( login_password_row )
    password_field = _field ( login_password_row , I18n . t ( "HASŁO" ) , "" , true )
    login_repeat_row = VBoxContainer . new ( )
    login_form . add_child ( login_repeat_row )
    repeat_password_field = _field ( login_repeat_row , I18n . t ( "POWTÓRZ HASŁO" ) , I18n . t ( "Wpisz hasło jeszcze raz" ) , true )


    login_password_row . visible = false
    login_repeat_row . visible = false
    name_field . text_submitted . connect ( func ( _text : String ) -> void : _submit_login_form ( ) )
    login_name_actions = HBoxContainer . new ( )
    login_name_actions . name = "EmpireNameActions"
    login_form . add_child ( login_name_actions )
    login_submit = _button ( "" , _submit_login_form , true )
    _login_style_button ( login_submit , true )
    login_submit . name = "CreateEmpireButton"
    login_submit . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    login_name_actions . add_child ( login_submit )
    login_name_cancel = _button ( I18n . t ( "Anuluj" ) , _cancel_name_stage )
    login_name_cancel . name = "CancelEmpireName"
    login_name_cancel . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    login_name_actions . add_child ( login_name_cancel )
    google_cancel_button = _button ( I18n . t ( "Anuluj logowanie Google" ) , _cancel_google_login )
    google_cancel_button . visible = false
    card . add_child ( google_cancel_button )
    login_retry_button = _button ( I18n . t ( "Ponów połączenie" ) , _retry )
    card . add_child ( login_retry_button )
    login_buttons = [ login_submit , login_retry_button , create_account_button ]
    connection_setup = VBoxContainer . new ( )
    connection_setup . add_theme_constant_override ( "separation" , 12 )
    connection_setup . visible = false

    card . add_child ( connection_setup )
    connection_hint = _label ( I18n . t ( "Adres serwera jest zapisany w aplikacji." ) , 19 , "a0b3a4" )
    connection_setup . add_child ( connection_hint )
    server_field = _field ( connection_setup , I18n . t ( "ADRES SERWERA" ) , "https://server.example" )
    server_field . max_length = 2048
    server_field . text_changed . connect ( _on_connection_edited )
    connection_setup . add_child ( _label ( I18n . t ( "Adres serwera jest już zapisany w aplikacji. Zmień go tylko po otrzymaniu nowego adresu od administratora gry." ) , 18 , "a0b3a4" ) )
    default_server_button = _button ( I18n . t ( "Użyj adresu z aplikacji" ) , _use_baked_server )
    connection_setup . add_child ( default_server_button )
    login_version_label = _label ( CLIENT_VERSION_NAME + I18n . t ( "  /  OTWARTA GALAKTYKA" ) , 18 , "7f9384" )
    stack . add_child ( login_version_label )
    _set_login_mode ( "" , false )


func _login_name_stage_active ( ) -> bool :
    return login_mode in [ "google_register" , "email_register" ]


func _sync_login_stage_visibility ( ) -> void :
    if not is_instance_valid ( login_name_panel ) :
        return
    var naming : bool = _login_name_stage_active ( )
    login_choice_panel . visible = not naming
    login_name_panel . visible = naming
    login_name_background . visible = naming
    login_form . visible = naming
    login_version_label . visible = not naming
    login_hero_spacer . visible = not naming
    if naming :
        google_login_button . visible = false
        email_login_button . visible = false
        create_account_button . visible = false
        google_cancel_button . visible = false
        login_retry_button . visible = false
        email_form . visible = false
        if login_announcement != null :
            login_announcement . hide ( )
    else :
        google_login_button . visible = true
        create_account_button . visible = true
        email_login_button . visible = email_login != null and email_login . configured
        email_form . visible = email_entry_open and email_login != null and email_login . configured
        google_cancel_button . visible = google_login != null and google_login . is_active ( ) and not google_reauth_dialog_visible ( )
    var notice_parent : Node = login_name_panel . get_child ( 0 ) if naming else login_choice_panel . get_child ( 0 )
    if login_notice . get_parent ( ) != notice_parent :
        login_notice . reparent ( notice_parent , false )
    login_name_cancel . disabled = update_required
    _update_login_art_layout ( )
    # Providers emit changed during success before completed; check an abandoned flow
    # only after completed has had a chance to enter the game or race selection.
    if naming and not login_name_flow_check_queued :
        login_name_flow_check_queued = true
        _check_name_stage_flow . call_deferred ( )


func _check_name_stage_flow ( ) -> void :
    login_name_flow_check_queued = false
    if not showing_login or update_required or not _login_name_stage_active ( ) :
        return
    var provider = email_login if login_mode == "email_register" else google_login
    if provider != null and provider . is_active ( ) :
        return
    _set_login_mode ( "" , false )
    _set_login_message ( I18n . t ( "Potwierdzenie logowania wygasło. Zaloguj się ponownie." ) , true )


func _update_login_art_layout ( ) -> void :
    if not is_instance_valid ( login_hero_spacer ) or not is_instance_valid ( login_scroll ) :
        return
    var naming : bool = _login_name_stage_active ( )
    var compact : bool = naming and login_screen . size . y < 644.0
    if naming :
        login_hero_spacer . custom_minimum_size . y = 0.0
        var panel_style : StyleBoxFlat = login_name_panel . get_theme_stylebox ( "panel" ) as StyleBoxFlat
        panel_style . set_content_margin_all ( 12.0 if compact else 24.0 )
        login_form . add_theme_constant_override ( "separation" , 6 if compact else 12 )
        login_form_title . add_theme_font_size_override ( "font_size" , 24 if compact else 28 )
        login_form_hint . add_theme_font_size_override ( "font_size" , 18 if compact else 20 )
        name_field . custom_minimum_size . y = 50 if compact else 80
        login_submit . custom_minimum_size . y = 58 if compact else 82
        login_name_cancel . custom_minimum_size . y = 48 if compact else 68
        return
    var with_bulletin : bool = login_announcement != null and is_instance_valid ( login_announcement . panel ) and login_announcement . panel . visible
    login_hero_spacer . custom_minimum_size . y = clampf ( login_scroll . size . y * ( 0.44 if with_bulletin else 0.55 ) , 120.0 , 900.0 )


func _begin_name_stage ( provider : String ) -> void :
    if not showing_login or update_required :
        return
    var next_mode : String = provider + "_register"
    var entering : bool = login_mode != next_mode
    login_mode = next_mode
    email_entry_open = false
    login_password_row . visible = false
    login_repeat_row . visible = false
    if entering :
        name_field . text = ""
        _set_login_message ( "" )
    password_field . text = ""
    repeat_password_field . text = ""
    login_form_title . text = I18n . t ( "Tworzenie imperium" )
    login_form_hint . text = I18n . t ( "Adres e-mail potwierdzony. Wybierz nazwę nowego imperium." ) if provider == "email" else I18n . t ( "Konto Google potwierdzone. Wybierz nazwę nowego imperium." )
    name_field . placeholder_text = I18n . t ( "3–20 znaków" )
    login_submit . text = I18n . t ( "Stwórz imperium" )
    _refresh_google_controls ( )
    _refresh_login_controls ( )
    if entering :
        _dismiss_login_keyboard ( )
        login_scroll . scroll_vertical = 0
        login_scroll . set_deferred ( "scroll_vertical" , 0 )


func _cancel_name_stage ( ) -> void :
    _dismiss_login_keyboard ( )
    if login_mode == "email_register" and email_login != null :
        email_login . cancel ( )
    elif google_login != null :
        google_login . cancel ( )
    _set_login_mode ( "" , false )
    _refresh_google_controls ( )


func _set_login_mode ( _mode : String , reveal : bool = true ) -> void :
    if reveal and ( request_pending or update_required ) :
        return
    if reveal and google_login != null and google_login . is_active ( ) :
        google_login . cancel ( )
    if reveal and email_login != null and email_login . is_active ( ) :
        email_login . cancel ( )
    email_entry_open = false
    if is_instance_valid ( email_form ) :
        email_form . visible = false


    login_mode = ""
    name_field . text = ""
    login_form . visible = false
    login_password_row . visible = false
    login_repeat_row . visible = false
    password_field . text = ""
    repeat_password_field . text = ""
    _set_login_message ( "" )
    _refresh_login_controls ( )


func _refresh_login_controls ( ) -> void :
    var google_busy : bool = google_login != null and google_login . is_active ( )
    var email_busy : bool = email_login != null and email_login . is_active ( )
    for button : Button in login_buttons :
        button . disabled = request_pending or update_required or google_busy or email_busy
    if is_instance_valid ( create_account_button ) :
        create_account_button . disabled = request_pending or update_required or google_busy or email_busy or ( ( google_login == null or not google_login . configured ) and ( email_login == null or not email_login . configured ) )
    if login_mode == "google_register" and google_login != null :
        login_submit . disabled = request_pending or update_required or google_login . is_request_pending ( )
    elif login_mode == "email_register" and email_login != null :
        login_submit . disabled = request_pending or update_required or email_login . is_request_pending ( )
    login_retry_button . visible = not session_token . is_empty ( ) or ( google_login != null and google_login . configuration_loaded and not google_login . configured )
    var editable : bool = not ( request_pending and request_kind == "auth" ) and ( not google_busy or login_mode == "google_register" ) and ( not email_busy or login_mode == "email_register" )
    for field : LineEdit in [ name_field , password_field , repeat_password_field ] :
        field . editable = editable
    _sync_login_stage_visibility ( )


func _dismiss_login_keyboard ( ) -> void :
    var focused : Control = get_viewport ( ) . gui_get_focus_owner ( )
    if focused != null and login_screen . is_ancestor_of ( focused ) :
        focused . release_focus ( )
    if DisplayServer . has_feature ( DisplayServer . FEATURE_VIRTUAL_KEYBOARD ) :
        DisplayServer . virtual_keyboard_hide ( )


func _set_login_message ( message : String , error : bool = false ) -> void :
    login_message_error = error
    login_notice . visible = not message . is_empty ( )
    login_message . text = message
    login_message . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ffe5e1" ) ) if error else _ui_color ( Color ( "e7eee4" ) ) )
    login_message_title . visible = error
    login_message_title . text = I18n . t ( "Nie udało się stworzyć imperium" ) if login_mode in [ "register" , "google_register" , "email_register" ] else I18n . t ( "Nie udało się zalogować" ) if login_mode == "login" else I18n . t ( "Nie udało się połączyć" )
    login_notice . add_theme_stylebox_override ( "panel" , _style ( "391c23" if error else "101010" , "ff9287" if error else "45654c" , 12 , 16 ) )
    if error :
        _dismiss_login_keyboard ( )
        _reveal_login_message . call_deferred ( )


func _reveal_login_message ( ) -> void :

    await get_tree ( ) . process_frame
    await get_tree ( ) . process_frame
    if is_inside_tree ( ) and login_notice . is_visible_in_tree ( ) and login_message_error :
        login_notice . grab_focus ( )
        login_scroll . ensure_control_visible ( login_notice )


func _submit_login_form ( ) -> void :
    if login_mode . is_empty ( ) or not login_form . is_visible_in_tree ( ) :
        return
    if ( login_mode == "google_register" and google_login != null ) or ( login_mode == "email_register" and email_login != null ) :
        var empire_name : String = name_field . text . strip_edges ( )
        if empire_name . length ( ) < 3 or empire_name . length ( ) > 20 :
            _set_login_message ( I18n . t ( "Nazwa musi mieć 3–20 znaków: litery, cyfry, spacje, _ lub -." ) , true )
            return
        _dismiss_login_keyboard ( )
        if login_mode == "email_register" :
            email_login . complete ( empire_name )
        else :
            google_login . complete ( empire_name )
        return



func _on_google_configuration ( ) -> void :
    if release_open and is_instance_valid ( release_panel ) and release_panel . mode == "account" :
        release_panel . set_status ( I18n . t ( "Potwierdź konto Google tego imperium w oknie systemowym." ) if google_login . configured else I18n . t ( "Logowanie Google jest chwilowo niedostępne. Sprawdź połączenie i spróbuj ponownie." ) , not google_login . configured )
    if showing_login and session_token . is_empty ( ) and not email_entry_open and not _login_name_stage_active ( ) :
        if google_login . configured :
            _set_login_message ( "" )
        else :
            _set_login_message ( I18n . t ( "Logowanie Google jest chwilowo niedostępne. Sprawdź połączenie i spróbuj ponownie." ) , true )
    _refresh_google_controls ( )
    _refresh_email_controls ( )


func _refresh_google_controls ( ) -> void :
    if not is_instance_valid ( google_login_button ) or google_login == null :
        return
    var active : bool = google_login . is_active ( )

    google_login_button . visible = true
    google_login_button . disabled = request_pending or update_required or active or not google_login . configured
    create_account_button . disabled = request_pending or update_required or active or ( email_login != null and email_login . is_active ( ) ) or not ( google_login . configured or ( email_login != null and email_login . configured ) )
    google_cancel_button . visible = active and not google_reauth_dialog_visible ( )
    var language_picker : Control = login_screen . find_child ( "LanguagePicker" , true , false ) as Control
    if is_instance_valid ( language_picker ) :
        language_picker . disabled = active or ( email_login != null and email_login . is_active ( ) )
    if google_reauth_dialog_visible ( ) :
        google_reauth_dialog . get_ok_button ( ) . disabled = active or update_required
    _refresh_login_controls ( )
    _refresh_email_controls ( )


func google_reauth_dialog_visible ( ) -> bool :
    return is_instance_valid ( google_reauth_dialog ) and google_reauth_dialog . visible


func _start_google_login ( ) -> void :
    if google_login == null or not google_login . configured or request_pending or update_required or google_login . is_active ( ) :
        return
    var connection : Dictionary = ServerAddressScript . parse_input ( server_field . text )
    if connection . has ( "error" ) :
        _set_login_message ( str ( connection [ "error" ] ) , true )
        return
    _dismiss_login_keyboard ( )
    _accept_connection ( connection )
    connection_editing = false


    session_token = ""
    _reset_world ( )
    _save_session ( )
    _set_login_mode ( "" , false )
    password_field . text = ""
    repeat_password_field . text = ""
    _set_login_message ( I18n . t ( "Wybierz konto Google w oknie systemowym." ) )
    google_login . start ( "login" )


func _create_account_from_login ( ) -> void :
    if request_pending or update_required or session_token != "" :
        return
    if google_login != null and google_login . configured :
        _start_google_login ( )
    elif email_login != null and email_login . configured :
        _open_email_login ( )
    else :
        _set_login_message ( I18n . t ( "Rejestracja chwilowo niedostępna. Spróbuj ponownie za moment." ) , true )


func _cancel_google_login ( ) -> void :
    if google_login != null :
        google_login . cancel ( )
    _set_login_mode ( "" , false )
    _set_login_message ( I18n . t ( "Logowanie Google zostało anulowane. Spróbuj ponownie." ) )


func _on_google_cancelled ( ) -> void :
    if google_reauth_dialog_visible ( ) :
        google_reauth_status . text = I18n . t ( "Logowanie Google zostało anulowane. Spróbuj ponownie." )
        google_reauth_status . add_theme_color_override ( "font_color" , _ui_color ( Color ( "a0b3a4" ) ) )
        _refresh_google_controls ( )
    else :
        _cancel_google_login ( )


func _on_google_name_needed ( ) -> void :
    _begin_name_stage ( "google" )


func _on_google_completed ( response : Dictionary , completed_mode : String ) -> void :
    if completed_mode == "reauthenticate" and str ( response . get ( "state" , { } ) . get ( "player" , { } ) . get ( "id" , "" ) ) != str ( state . get ( "player" , { } ) . get ( "id" , "" ) ) :
        _on_google_failed ( I18n . t ( "Wybrane konto Google nie należy do tego imperium. Wybierz właściwe konto." ) )
        return


    var timed_operation : String = ""
    if completed_mode == "login" :
        timed_operation = "register" if login_mode == "google_register" else "login"
    var apply_started : int = Time . get_ticks_msec ( )
    if is_instance_valid ( google_reauth_dialog ) :
        google_reauth_dialog . hide ( )
    var return_to_account : bool = completed_mode == "reauthenticate" and release_open and is_instance_valid ( release_panel ) and release_panel . mode == "account"
    _handle_response ( "auth" , HTTPRequest . RESULT_SUCCESS , 200 , JSON . stringify ( response ) . to_utf8_buffer ( ) )
    if return_to_account :

        _open_release_panel ( "account" )
    if completed_mode == "reauthenticate" :
        _notify ( I18n . t ( "Konto Google tego imperium zostało ponownie potwierdzone." ) )
    _refresh_google_controls ( )
    if not timed_operation . is_empty ( ) :
        AuthTiming . record ( timed_operation , { "apply_ms" : Time . get_ticks_msec ( ) - apply_started } , HTTPRequest . RESULT_SUCCESS , 200 )


func _on_google_failed ( message : String ) -> void :
    if is_instance_valid ( google_reauth_dialog ) and google_reauth_dialog . visible :
        google_reauth_status . text = message
        google_reauth_status . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ff9287" ) ) )
    else :
        if login_mode == "google_register" and not google_login . waiting_for_name ( ) :
            _set_login_mode ( "" , false )
        _set_login_message ( message , true )
    _refresh_google_controls ( )


func _refresh_email_controls ( ) -> void :
    if not is_instance_valid ( email_login_button ) or email_login == null :
        return
    var active : bool = email_login . is_active ( )
    var waiting : bool = email_login . phase == "waiting"
    var naming : bool = login_mode == "email_register"
    email_login_button . visible = email_login . configured
    email_login_button . disabled = request_pending or update_required or active
    email_form . visible = email_entry_open and email_login . configured
    email_form . get_child ( 0 ) . visible = not naming
    email_field . get_parent ( ) . visible = not naming
    email_field . editable = not active
    email_send_button . visible = not active and not naming
    email_send_button . disabled = request_pending or update_required
    email_wait_label . visible = active and not naming
    if email_login . phase == "sending" :
        email_wait_label . text = I18n . t ( "Wysyłanie linku do logowania…" )
    elif email_login . phase == "completing" :
        email_wait_label . text = I18n . t ( "Łączenie…" )
    else :
        email_wait_label . text = I18n . t ( "Sprawdź pocztę. Otwórz link na tym telefonie, potwierdź logowanie i wybierz „Wróć do gry”." )
    email_resend_button . visible = waiting
    var remaining : int = email_login . resend_wait_seconds ( )
    email_resend_button . text = I18n . t ( "Wyślij link ponownie za %s s" ) % str ( remaining ) if remaining > 0 else I18n . t ( "Wyślij link ponownie" )
    email_resend_button . disabled = remaining > 0 or email_login . is_request_pending ( ) or update_required
    email_cancel_button . disabled = update_required
    var picker : Control = login_screen . find_child ( "LanguagePicker" , true , false ) as Control
    if is_instance_valid ( picker ) :
        picker . disabled = active or ( google_login != null and google_login . is_active ( ) )
    if is_instance_valid ( email_reauth_dialog ) and email_reauth_dialog . visible :
        email_reauth_field . editable = not active
        email_reauth_dialog . get_ok_button ( ) . text = email_resend_button . text if waiting else I18n . t ( "Wyślij link do logowania" )
        email_reauth_dialog . get_ok_button ( ) . disabled = request_pending or update_required or email_login . is_request_pending ( ) or ( active and not waiting ) or ( waiting and remaining > 0 )
        if active :
            email_reauth_status . text = email_wait_label . text
    _refresh_login_controls ( )


func _open_email_login ( ) -> void :
    if email_login == null or not email_login . configured or request_pending or update_required :
        return
    if google_login != null :
        google_login . cancel ( )
    email_login . cancel ( )
    _set_login_mode ( "" , false )
    email_entry_open = true
    email_field . text = ""
    _set_login_message ( "" )
    _refresh_google_controls ( )
    email_field . grab_focus ( )
    login_scroll . ensure_control_visible . call_deferred ( email_field )


func _send_email_login ( ) -> void :
    if email_login == null or not email_login . configured or not email_entry_open or request_pending or update_required or email_login . is_active ( ) :
        return
    var address : String = email_field . text . strip_edges ( )
    var connection : Dictionary = ServerAddressScript . parse_input ( server_field . text )
    if connection . has ( "error" ) :
        _set_login_message ( str ( connection [ "error" ] ) , true )
        return
    _dismiss_login_keyboard ( )
    _accept_connection ( connection )
    connection_editing = false

    session_token = ""
    _reset_world ( )
    _save_session ( )
    _set_login_mode ( "" , false )
    email_entry_open = true
    email_field . text = address
    _set_login_message ( "" )
    email_login . start ( address )
    _refresh_google_controls ( )


func _resend_email_login ( ) -> void :
    if email_login == null or update_required or request_pending :
        return
    _set_login_message ( "" )
    email_login . resend ( )


func _cancel_email_login ( ) -> void :
    if email_login != null :
        email_login . cancel ( )
    _set_login_mode ( "" , false )
    email_field . text = ""
    _set_login_message ( "" )
    _refresh_google_controls ( )


func _on_email_name_needed ( ) -> void :
    _begin_name_stage ( "email" )


func _on_email_completed ( response : Dictionary ) -> void :
    if update_required :
        return
    var reauthenticating : bool = is_instance_valid ( email_reauth_dialog ) and email_reauth_dialog . visible
    if reauthenticating and str ( response . get ( "state" , { } ) . get ( "player" , { } ) . get ( "id" , "" ) ) != str ( state . get ( "player" , { } ) . get ( "id" , "" ) ) :
        _on_email_failed ( I18n . t ( "Ten adres e-mail nie jest połączony z tym imperium." ) )
        return
    var return_to_account : bool = reauthenticating and release_open and is_instance_valid ( release_panel ) and release_panel . mode == "account"
    var operation : String = "register" if login_mode == "email_register" else "login"
    var apply_started : int = Time . get_ticks_msec ( )
    if is_instance_valid ( email_reauth_dialog ) :
        email_reauth_dialog . hide ( )
        email_reauth_field . text = ""
    _handle_response ( "auth" , HTTPRequest . RESULT_SUCCESS , 200 , JSON . stringify ( response ) . to_utf8_buffer ( ) )
    if return_to_account :
        _open_release_panel ( "account" )
    if reauthenticating :
        _notify ( I18n . t ( "Adres e-mail tego imperium został ponownie potwierdzony." ) )
    email_entry_open = false
    email_field . text = ""
    _refresh_google_controls ( )
    if not reauthenticating :
        AuthTiming . record ( operation , { "apply_ms" : Time . get_ticks_msec ( ) - apply_started } , HTTPRequest . RESULT_SUCCESS , 200 )


func _on_email_failed ( message : String ) -> void :
    if is_instance_valid ( email_reauth_dialog ) and email_reauth_dialog . visible :
        email_reauth_status . text = message
        email_reauth_status . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ff9287" ) ) )
        _refresh_google_controls ( )
        return
    if login_mode == "email_register" and not email_login . waiting_for_name ( ) :
        _set_login_mode ( "" , false )
    _set_login_message ( message , true )
    _refresh_google_controls ( )


func _open_email_reauth ( ) -> void :
    if email_login == null or session_token . is_empty ( ) or request_pending or update_required or email_login . is_active ( ) :
        return
    if not bool ( state . get ( "account" , { } ) . get ( "email_linked" , false ) ) :
        return
    if not email_login . configured :
        _account_error ( I18n . t ( "Logowanie e-mail jest chwilowo niedostępne. Spróbuj ponownie później." ) )
        email_login . load_configuration ( )
        return
    if google_login != null :
        google_login . cancel ( )
    if not is_instance_valid ( email_reauth_dialog ) :
        email_reauth_dialog = ConfirmationDialog . new ( )
        email_reauth_dialog . name = "EmailAccountConfirmation"
        email_reauth_dialog . dialog_autowrap = true
        email_reauth_dialog . dialog_hide_on_ok = false
        add_child ( email_reauth_dialog )
        var body : VBoxContainer = VBoxContainer . new ( )
        body . add_theme_constant_override ( "separation" , 14 )
        email_reauth_dialog . add_child ( body )
        email_reauth_status = _label ( "" , 21 , "a0b3a4" )
        body . add_child ( email_reauth_status )
        email_reauth_field = _field ( body , I18n . t ( "ADRES E-MAIL" ) , "name@example.com" )
        email_reauth_field . virtual_keyboard_type = LineEdit . KEYBOARD_TYPE_EMAIL_ADDRESS
        email_reauth_field . max_length = 254
        email_reauth_dialog . confirmed . connect ( _confirm_email_reauth )
        email_reauth_dialog . canceled . connect ( _cancel_email_reauth )
    email_reauth_field . text = ""
    email_reauth_status . text = I18n . t ( "Wpisz adres e-mail używany do tego imperium. Po potwierdzeniu ponownie wybierz operację." )
    email_reauth_status . add_theme_color_override ( "font_color" , _ui_color ( Color ( "a0b3a4" ) ) )
    email_reauth_dialog . title = I18n . t ( "Potwierdź adres e-mail" )
    email_reauth_dialog . get_cancel_button ( ) . text = I18n . t ( "Wróć" )
    email_reauth_dialog . popup_centered_clamped ( Vector2i ( 600 , 420 ) , 0.9 )
    _refresh_email_controls ( )


func _confirm_email_reauth ( ) -> void :
    if email_login == null or session_token . is_empty ( ) or request_pending or update_required or not bool ( state . get ( "account" , { } ) . get ( "email_linked" , false ) ) :
        return
    if email_login . phase == "waiting" :
        email_login . resend ( )
    elif not email_login . is_active ( ) :
        email_reauth_status . add_theme_color_override ( "font_color" , _ui_color ( Color ( "a0b3a4" ) ) )
        email_login . start ( email_reauth_field . text )


func _cancel_email_reauth ( ) -> void :
    if email_login != null :
        email_login . cancel ( )
    if is_instance_valid ( email_reauth_dialog ) :
        email_reauth_dialog . hide ( )
        email_reauth_field . text = ""


func _open_google_reauth ( ) -> void :
    if bool ( state . get ( "account" , { } ) . get ( "email_linked" , false ) ) and not bool ( state . get ( "account" , { } ) . get ( "google_linked" , false ) ) :
        _open_email_reauth ( )
        return
    if google_login == null or session_token . is_empty ( ) or request_pending or update_required or google_login . is_active ( ) :
        return
    if not bool ( state . get ( "account" , { } ) . get ( "google_linked" , false ) ) :
        return
    if not google_login . configured :
        _account_error ( I18n . t ( "Łączenie…" ) )
        google_login . load_configuration ( )
        return
    if not is_instance_valid ( google_reauth_dialog ) :
        google_reauth_dialog = ConfirmationDialog . new ( )
        google_reauth_dialog . name = "GoogleAccountConfirmation"
        google_reauth_dialog . dialog_autowrap = true
        google_reauth_dialog . dialog_hide_on_ok = false
        add_child ( google_reauth_dialog )
        var body : VBoxContainer = VBoxContainer . new ( )
        body . add_theme_constant_override ( "separation" , 14 )
        google_reauth_dialog . add_child ( body )
        google_reauth_status = _label ( "" , 21 , "a0b3a4" )
        body . add_child ( google_reauth_status )
        google_reauth_dialog . confirmed . connect ( _confirm_google_reauth )
        google_reauth_dialog . canceled . connect ( func ( ) -> void : google_login . cancel ( ) )
    google_reauth_dialog . title = I18n . t ( "Potwierdź konto Google" )
    google_reauth_dialog . get_ok_button ( ) . text = I18n . t ( "Kontynuuj z Google" )
    google_reauth_dialog . get_cancel_button ( ) . text = I18n . t ( "Wróć" )
    google_reauth_status . text = I18n . t ( "Potwierdź konto Google tego imperium w oknie systemowym." )
    google_reauth_status . add_theme_color_override ( "font_color" , _ui_color ( Color ( "a0b3a4" ) ) )
    google_reauth_dialog . popup_centered_clamped ( Vector2i ( 600 , 280 ) , 0.9 )
    _refresh_google_controls ( )


func _confirm_google_reauth ( ) -> void :
    if google_login == null or google_login . is_active ( ) or session_token . is_empty ( ) or request_pending or update_required or not bool ( state . get ( "account" , { } ) . get ( "google_linked" , false ) ) :
        return
    var current_player_id : String = str ( state . get ( "player" , { } ) . get ( "id" , "" ) )
    if current_player_id . is_empty ( ) :
        _on_google_failed ( I18n . t ( "Zaloguj się ponownie przed zmianą ustawień konta." ) )
        return
    google_reauth_status . text = I18n . t ( "Wybierz konto Google w oknie systemowym." )

    google_login . start ( "login" , "" , current_player_id )


func _make_update_overlay ( ) -> void :
    update_overlay = Control . new ( )
    update_overlay . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    update_overlay . mouse_filter = Control . MOUSE_FILTER_STOP
    update_overlay . visible = false
    add_child ( update_overlay )
    var shade : ColorRect = ColorRect . new ( )
    shade . color = _ui_color ( Color ( "08110d" ) )
    shade . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    shade . mouse_filter = Control . MOUSE_FILTER_IGNORE
    update_overlay . add_child ( shade )
    update_margin = MarginContainer . new ( )
    update_margin . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    for side : String in [ "left" , "top" , "right" , "bottom" ] :
        update_margin . add_theme_constant_override ( "margin_" + side , 22 )
    update_overlay . add_child ( update_margin )
    var scroll : ScrollContainer = TouchScrollScript . new ( )
    scroll . horizontal_scroll_mode = ScrollContainer . SCROLL_MODE_DISABLED
    scroll . follow_focus = true
    update_margin . add_child ( scroll )
    var stack : VBoxContainer = VBoxContainer . new ( )
    stack . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    stack . add_theme_constant_override ( "separation" , 24 )
    scroll . add_child ( stack )
    var brand : HBoxContainer = _row ( stack )
    brand . add_child ( _brand_icon ( 44 ) )
    brand . add_child ( _label ( GAME_TITLE , 26 , "a4ef77" ) )
    var card : VBoxContainer = _card ( stack )
    card . add_theme_constant_override ( "separation" , 24 )
    update_title = _label ( I18n . t ( "Dostępna aktualizacja" ) , 34 )
    card . add_child ( update_title )
    update_description = _label ( "" , 24 , "c9d9cb" )
    card . add_child ( update_description )
    update_status = _label ( "" , 21 , "e6b774" )
    card . add_child ( update_status )
    play_update_progress = _meter("72b8f4")
    play_update_progress.custom_minimum_size.y = 28
    play_update_progress.hide()
    card.add_child(play_update_progress)
    update_download_button = _button ( I18n.t("Pobierz aktualizację"), _start_play_update, true )
    card . add_child ( update_download_button )
    update_retry_button = _button ( I18n . t ( "Sprawdź ponownie" ) , _check_client_version )
    card . add_child ( update_retry_button )
    update_later_button = _button ( I18n . t ( "Później" ) , _dismiss_update )
    card . add_child ( update_later_button )
    card . add_child ( _label ( I18n . t ( "Aktualizacje aplikacji są instalowane przez Google Play. Twoje imperium i świat gry pozostają na serwerze." ) , 21 , "a0b3a4" ) )


func _sync_screen_visibility ( ) -> void :


    var covered : bool = is_instance_valid ( update_overlay ) and update_overlay . visible
    var choosing : bool = not showing_login and _needs_race_choice ( )
    login_screen . visible = showing_login and not covered and not release_open
    app_screen . visible = not showing_login and not choosing and not covered and not skill_open and not release_open and not ( communications != null and communications . visible ) and not ( alliance_ui != null and alliance_ui . visible ) and not ( ranking_ui != null and ranking_ui.visible )
    if is_instance_valid ( skill_overlay ) :
        skill_overlay . visible = skill_open and not showing_login and not choosing and not covered
    if is_instance_valid ( race_screen ) :
        race_screen . visible = choosing and not covered and not release_open
    if is_instance_valid ( release_panel ) :
        release_panel . visible = release_open and not covered


func _show_update ( ) -> void :
    if review_prompt != null:
        review_prompt.hide()
    if ranking_ui != null :
        ranking_ui.close()
    if alliance_ui != null :
        alliance_ui . close ( )
    if communications != null :
        communications . close ( )
    if is_instance_valid ( cancel_project_dialog ) :
        cancel_project_dialog . hide ( )
    if compact_ui != null :
        compact_ui . close_details ( )
    var was_visible : bool = update_overlay . visible
    update_title . text = I18n . t ( "Wymagana aktualizacja" ) if update_required else I18n . t ( "Dostępna aktualizacja" )
    var latest_name : String = str ( update_manifest . get ( "latest_version" , "" ) )
    var description : String = I18n . t ( "Zaktualizuj grę w Google Play, aby kontynuować." ) if update_required else I18n . t ( "Nowa wersja gry jest dostępna w Google Play." )
    if not latest_name . is_empty ( ) :
        description += I18n . t ( "\nWersja " ) + latest_name + I18n . t ( " • Twoja: " ) + CLIENT_VERSION_NAME
    var release_message : String = str ( update_manifest . get ( "message" , "" ) )
    if not release_message . is_empty ( ) :
        description += "\n\n" + release_message
    update_description . text = description
    update_later_button . visible = not update_required
    update_retry_button . disabled = update_request_pending
    update_download_button . disabled = false
    update_status . text = I18n . t ( "Aktualizacja zostanie pobrana i zainstalowana przez Google Play." )
    if update_required :
        update_status . text += "\n" + I18n . t ( "Brak przycisku Aktualizuj? Sprawdź konto Google używane w Google Play i spróbuj później." )
    update_overlay . visible = true
    _sync_play_update()
    _sync_screen_visibility ( )
    if not was_visible :
        DisplayServer . virtual_keyboard_hide ( )
        update_download_button . grab_focus . call_deferred ( )


func _dismiss_update ( ) -> void :
    if update_required :
        return
    dismissed_update_codes [ server_url ] = int ( update_manifest . get ( "latest_version_code" , 0 ) )
    update_overlay . visible = false
    _sync_screen_visibility ( )


func _open_google_play_update ( ) -> void :
    if connection_editing :
        return
    var error : Error = ERR_CANT_OPEN
    if OS . get_name ( ) == "Android" :
        error = OS . shell_open ( "market://details?id=" + PLAY_STORE_PACKAGE_ID )
    if error != OK :
        error = OS . shell_open ( PLAY_STORE_WEB_URL )
    if error == OK :
        update_status . text = I18n . t ( "Google Play zostało otwarte. Wybierz „Aktualizuj”, aby zainstalować nową wersję." )
    else :
        update_status . text = I18n . t ( "Nie udało się otworzyć Google Play. Otwórz sklep ręcznie i wyszukaj Alien Colonies." )


func _cancel_update_check ( ) -> void :


    update_request_generation += 1
    update_request_pending = false
    if is_instance_valid ( update_http ) :
        update_http . cancel_request ( )
        update_http . queue_free ( )
    update_http = null
    if is_instance_valid ( update_retry_button ) :
        update_retry_button . disabled = false


func _reset_update_origin ( ) -> void :
    _cancel_update_check ( )
    update_required = false
    update_manifest . clear ( )
    update_overlay . visible = false
    _sync_screen_visibility ( )




func _check_client_version ( ) -> void :
    if update_request_pending or connection_editing or server_url . is_empty ( ) :
        return
    update_request_generation += 1
    var generation : int = update_request_generation
    var origin : String = server_url
    update_http = HTTPRequest . new ( )
    update_http . timeout = 8.0
    update_http . max_redirects = 0
    update_http . body_size_limit = 16384
    add_child ( update_http )
    update_http . request_completed . connect ( _on_update_response . bind ( origin , generation ) )
    update_request_pending = true
    update_retry_button . disabled = true
    if update_overlay . visible :
        update_status . text = I18n . t ( "Sprawdzanie aktualizacji…" )
    var headers : PackedStringArray = PackedStringArray ( [ "Accept: application/json" , "Accept-Language: " + I18n . locale , "X-PGR-Client-Version: " + str ( CLIENT_VERSION_CODE ) ] )
    var error : Error = update_http . request ( origin + "/api/client-version" , headers , HTTPClient . METHOD_GET )
    if error != OK :
        _cancel_update_check ( )
        _update_check_failed ( )


func _update_check_failed ( ) -> void :


    if update_overlay . visible :
        update_status . text = I18n . t ( "Nie udało się sprawdzić aktualizacji. Sprawdź internet i spróbuj ponownie." )


func _on_update_response ( result : int , response_code : int , _headers : PackedStringArray , body : PackedByteArray , origin : String , generation : int ) -> void :
    if generation != update_request_generation or origin != server_url or connection_editing :
        return
    update_request_pending = false
    if is_instance_valid ( update_http ) :
        update_http . queue_free ( )
    update_http = null
    update_retry_button . disabled = false
    if response_code == 426 :
        var rejected : Variant = JSON . parse_string ( body . get_string_from_utf8 ( ) )
        _handle_required_update ( rejected . get ( "update" ) if rejected is Dictionary else null )
        return
    if result != HTTPRequest . RESULT_SUCCESS :
        _update_check_failed ( )
        return
    var parsed : Variant = JSON . parse_string ( body . get_string_from_utf8 ( ) )
    if response_code != 200 or not parsed is Dictionary :
        _update_check_failed ( )
        return
    if typeof ( parsed . get ( "ok" ) ) != TYPE_BOOL or not bool ( parsed [ "ok" ] ) :
        _update_check_failed ( )
        return
    var manifest : Dictionary = UpdatePolicyScript . parse_manifest ( parsed , CLIENT_VERSION_CODE )
    if manifest . is_empty ( ) :
        _update_check_failed ( )
        return
    var was_required : bool = update_required
    update_manifest = manifest
    update_required = bool ( manifest [ "required" ] )
    var dismissed : bool = int ( dismissed_update_codes . get ( server_url , -1 ) ) == int ( manifest [ "latest_version_code" ] )
    if update_required or ( bool ( manifest [ "available" ] ) and not dismissed ) :
        _show_update ( )
    else :
        update_overlay . visible = false
        _sync_screen_visibility ( )
    if was_required and not update_required :
        _poll ( )


func _handle_required_update ( raw_manifest : Variant ) -> void :


    _cancel_update_check ( )
    update_required = true
    var manifest : Dictionary = UpdatePolicyScript . parse_manifest ( raw_manifest , CLIENT_VERSION_CODE )

    if not manifest . is_empty ( ) :
        update_manifest = manifest


    _invalidate_quote ( )
    _show_update ( )


func _make_app ( ) -> void :
    app_screen = _margin ( )
    app_screen . visible = false
    var shell : VBoxContainer = VBoxContainer . new ( )
    shell . add_theme_constant_override ( "separation" , 10 )
    app_screen . add_child ( shell )
    var brand : HBoxContainer = _row ( shell )
    brand . add_child ( _brand_icon ( 52 ) )
    planet_picker = _choice ( I18n . t ( "Wybierz swoją planetę" ) , 64 )
    planet_picker . item_selected . connect ( _select_owned_planet )
    brand . add_child ( planet_picker )
    connection_indicator = _label ( "●" , 22 , "91c89b" )
    connection_indicator . size_flags_horizontal = Control . SIZE_SHRINK_END
    connection_indicator . size_flags_vertical = Control . SIZE_SHRINK_CENTER
    brand . add_child ( connection_indicator )
    var menu : Button = _button ( "" , func ( ) -> void : options_panel . get_parent ( ) . visible = not options_panel . get_parent ( ) . visible )
    menu . name = "SettingsButton"
    menu . icon = _texture ( "settings" )
    menu . expand_icon = true
    menu . add_theme_constant_override ( "icon_max_width" , 30 )
    menu . tooltip_text = I18n . t ( "Ustawienia i połączenie" )
    menu . custom_minimum_size = Vector2 ( 64 , 64 )
    menu . size_flags_horizontal = Control . SIZE_SHRINK_END
    brand . add_child ( menu )
    options_panel = _card ( shell )
    options_panel . name = "SettingsPanel"
    options_panel . get_parent ( ) . visible = false
    options_panel . add_child ( _label ( GAME_TITLE + " · " + CLIENT_VERSION_NAME , 22 ) )
    _add_language_picker ( options_panel )
    _add_description_setting ( options_panel )
    clock_label = _label ( I18n . t ( "Łączenie…" ) , 22 , "94ab9a" )
    options_panel . add_child ( clock_label )
    var actions : HBoxContainer = _row ( options_panel )
    actions . add_child ( _button ( I18n . t ( "Odśwież" ) , _retry ) )
    actions . add_child ( _button ( I18n . t ( "Wyloguj" ) , _logout ) )
    var account_actions : HBoxContainer = _row ( options_panel )
    account_actions . add_child ( _button ( I18n . t ( "Konto" ) , _open_release_panel . bind ( "account" ) ) )
    account_actions . add_child ( _button ( I18n . t ( "Pomoc" ) , _open_release_panel . bind ( "help" ) ) )
    _make_resource_hud ( shell )
    skill_wallet_button = _button ( I18n . t ( "Kryształy Roju · 0    Koło umiejętności ›" ) , _open_skill_wheel )
    skill_wallet_button . name = "SwarmCrystalWallet"
    skill_wallet_button . custom_minimum_size . y = 56
    skill_wallet_button . add_theme_font_size_override ( "font_size" , 22 )
    skill_wallet_button . add_theme_color_override ( "font_color" , _ui_color ( Color ( "edc77a" ) ) )
    skill_wallet_button . tooltip_text = I18n . t ( "Osobny łup z Roju. Flota musi wrócić do bazy. Wydajesz go w kole umiejętności." )
    skill_wallet_button . visible = false
    shell . add_child ( skill_wallet_button )
    var attack_body : VBoxContainer = _card ( shell )
    incoming_banner = attack_body . get_parent ( ) as Control
    incoming_banner . name = "IncomingAttackBanner"
    incoming_banner . add_theme_stylebox_override ( "panel" , _style ( "321b1c" , "b95451" , 12 , 10 ) )
    incoming_banner . visible = false
    var attack_row : HBoxContainer = _row ( attack_body )
    incoming_summary = _label ( "" , 21 , "ffb1a8" )
    incoming_summary . autowrap_mode = TextServer . AUTOWRAP_OFF
    incoming_summary . clip_text = true
    incoming_summary . custom_minimum_size . y = 56
    incoming_summary . vertical_alignment = VERTICAL_ALIGNMENT_CENTER
    incoming_summary . text_overrun_behavior = TextServer . OVERRUN_TRIM_ELLIPSIS
    attack_row . add_child ( incoming_summary )
    incoming_button = _button ( I18n . t ( "Obrona" ) , _open_release_panel . bind ( "attacks" ) )
    incoming_button . custom_minimum_size = Vector2 ( 126 , 64 )
    incoming_button . size_flags_horizontal = Control . SIZE_SHRINK_END
    attack_row . add_child ( incoming_button )
    var active_body : VBoxContainer = _card ( shell )
    active_project = active_body . get_parent ( ) as Control
    active_project . name = "ActiveProject"
    active_project . visible = false
    active_project . add_theme_stylebox_override ( "panel" , _style ( "101010" , "262626" , 12 , 10 ) )
    var active_row : HBoxContainer = _row ( active_body )
    active_row . add_child ( _icon ( "time" , 24 ) )
    active_project_title = _label ( "" , 22 , "d4ebd6" )
    active_project_title . autowrap_mode = TextServer . AUTOWRAP_OFF
    active_project_title . text_overrun_behavior = TextServer . OVERRUN_TRIM_ELLIPSIS
    active_project_title . clip_text = true
    active_row . add_child ( active_project_title )
    active_project_time = _token_label ( "" , 22 , "d4ebd6" )
    active_row . add_child ( active_project_time )
    cancel_project_button = _button ( I18n . t ( "Anuluj" ) , _ask_cancel_project )
    cancel_project_button . name = "CancelProject"
    cancel_project_button . custom_minimum_size = Vector2 ( 110 , 52 )
    cancel_project_button . size_flags_horizontal = Control . SIZE_SHRINK_END
    cancel_project_button . add_theme_font_size_override ( "font_size" , 20 )
    active_row . add_child ( cancel_project_button )
    active_project_bar = _meter ( "91c89b" )
    active_project_bar . custom_minimum_size . y = 14
    active_body . add_child ( active_project_bar )
    connection_label = _label ( I18n . t ( "Połączono" ) , 17 , "91c89b" )
    connection_label . visible = false
    shell . add_child ( connection_label )
    var pages : Control = Control . new ( )
    pages . size_flags_vertical = Control . SIZE_EXPAND_FILL
    shell . add_child ( pages )
    for index : int in range ( 5 ) :
        var scroll : ScrollContainer = TouchScrollScript . new ( )
        scroll . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
        scroll . horizontal_scroll_mode = ScrollContainer . SCROLL_MODE_DISABLED
        scroll . follow_focus = true
        scroll . visible = index == 0
        pages . add_child ( scroll )
        var body : VBoxContainer = VBoxContainer . new ( )
        body . size_flags_horizontal = Control . SIZE_EXPAND_FILL
        body . add_theme_constant_override ( "separation" , 16 )
        scroll . add_child ( body )
        tabs . append ( scroll )
        tab_bodies . append ( body )
    fleet_action_bar = PanelContainer . new ( )
    fleet_action_bar . name = "FleetActionDock"
    fleet_action_bar . visible = false
    fleet_action_bar . add_theme_stylebox_override ( "panel" , _style ( "101010" , "262626" , 12 , 10 ) )
    shell . add_child ( fleet_action_bar )
    _make_planet_tab ( tab_bodies [ 0 ] )
    _make_galaxy_tab ( tab_bodies [ 1 ] )
    _make_fleet_tab ( tab_bodies [ 2 ] )
    _make_research_tab ( tab_bodies [ 3 ] )
    _make_reports_tab ( tab_bodies [ 4 ] )
    var navigation : HBoxContainer = _row ( shell )
    navigation . add_theme_constant_override ( "separation" , 5 )
    var nav_icons : Array [ String ] = [ "planet" , "galaxy" , "fleet" , "research" , "reports" ]
    for index : int in range ( 5 ) :
        var button : Button = _button ( "" , _open_navigation_tab . bind ( index ) )
        button . custom_minimum_size = Vector2 ( 0 , 92 )
        button . tooltip_text = I18n . t ( NAV_LABELS [ index ] ) . capitalize ( )
        button . add_theme_stylebox_override ( "normal" , _style ( "151515" , "262626" , 12 , 6 ) )
        navigation . add_child ( button )
        var content : VBoxContainer = VBoxContainer . new ( )
        content . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
        content . offset_top = 9
        content . offset_bottom = -9
        content . mouse_filter = Control . MOUSE_FILTER_IGNORE
        content . add_theme_constant_override ( "separation" , 4 )
        button . add_child ( content )
        var icon : TextureRect = _icon ( nav_icons [ index ] , 32 )
        content . add_child ( icon )
        var caption : Label = _label ( I18n . t ( NAV_LABELS [ index ] ) . capitalize ( ) , 22 )
        caption . horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
        content . add_child ( caption )
        button . set_meta ( "caption" , caption )
        nav_buttons . append ( button )
    _open_tab ( 0 )
    _make_race_screen ( )


func _race_definitions ( ) -> Array [ Dictionary ] :
    var result : Array [ Dictionary ] = [ ]
    var supplied : Variant = state . get ( "races" , [ ] )
    if not supplied is Array :
        return result
    for candidate : Variant in supplied :
        if candidate is Dictionary and str ( candidate . get ( "id" , "" ) ) in ArtLibrary . RACES :
            result . append ( candidate )
    return result


func _selected_race ( ) -> Dictionary :
    var id : String = str ( state . get ( "player" , { } ) . get ( "race_id" , "" ) )
    for definition : Dictionary in _race_definitions ( ) :
        if str ( definition . get ( "id" , "" ) ) == id :
            return definition
    return { }


func _needs_race_choice ( ) -> bool :

    return not _race_definitions ( ) . is_empty ( ) and str ( state . get ( "player" , { } ) . get ( "race_id" , "" ) ) . is_empty ( )


func _server_text ( value : Variant , fallback : String = "" ) -> String :



    var text : String = "" if value == null else str ( value )
    if text . is_empty ( ) :
        text = fallback
    return I18n . t ( text )


func _make_race_screen ( ) -> void :
    race_screen = _margin ( )
    race_screen . name = "RaceSelection"
    race_screen . visible = false
    race_scroll = TouchScrollScript . new ( )
    race_scroll . name = "RaceScroll"
    race_scroll . horizontal_scroll_mode = ScrollContainer . SCROLL_MODE_DISABLED
    race_scroll . follow_focus = true
    race_screen . add_child ( race_scroll )
    var stack : VBoxContainer = VBoxContainer . new ( )
    stack . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    stack . add_theme_constant_override ( "separation" , 18 )
    race_scroll . add_child ( stack )
    var brand : HBoxContainer = _row ( stack )
    brand . add_child ( _brand_icon ( 56 ) )
    brand . add_child ( _label ( GAME_TITLE , 30 , "a4ef77" ) )
    stack . add_child ( _label ( I18n . t ( "Wybierz swoją cywilizację" ) , 34 ) )
    stack . add_child ( _label ( I18n . t ( "Trzy rasy. Własne budynki, floty i uzbrojenie. Wybór rasy jest stały dla tego imperium." ) , 22 , "c9d9cb" ) )
    race_status = _label ( I18n . t ( "Wybierz rasę, aby rozpocząć rozwój kolonii." ) , 22 , "a5d5ac" )
    stack . add_child ( race_status )
    var actions : HBoxContainer = _row ( stack )
    race_retry_button = _button ( I18n . t ( "Odśwież" ) , _retry )
    race_logout_button = _button ( I18n . t ( "Wyloguj" ) , _logout )
    actions . add_child ( race_retry_button )
    actions . add_child ( race_logout_button )
    race_cards = VBoxContainer . new ( )
    race_cards . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    race_cards . add_theme_constant_override ( "separation" , 24 )
    stack . add_child ( race_cards )


func _clear_race_cards ( ) -> void :
    race_signature = ""
    race_error_message = ""
    race_buttons . clear ( )
    if is_instance_valid ( race_cards ) :
        _clear ( race_cards )
        race_scroll . scroll_vertical = 0
        race_status . text = I18n . t ( "Wybierz rasę, aby rozpocząć rozwój kolonii." )


func _refresh_race_screen ( ) -> void :
    if not is_instance_valid ( race_screen ) :
        _make_race_screen ( )
    if not _needs_race_choice ( ) :
        if not race_signature . is_empty ( ) :
            _clear_race_cards ( )
        return
    var definitions : Array [ Dictionary ] = _race_definitions ( )
    var signature : String = JSON . stringify ( definitions )
    if signature != race_signature :
        _clear_race_cards ( )
        race_signature = signature
        for definition : Dictionary in definitions :
            var id : String = str ( definition [ "id" ] )
            var card : VBoxContainer = _card ( race_cards )
            card . name = "Race_" + id
            card . add_theme_constant_override ( "separation" , 12 )
            var portrait_row : HBoxContainer = _row ( card )
            portrait_row . add_theme_constant_override ( "separation" , 18 )
            var portrait : TextureRect = TextureRect . new ( )
            portrait . texture = ArtLibrary . texture ( str ( definition . get ( "portrait_art" , "races/" + id + "/portrait" ) ) )
            portrait . custom_minimum_size = Vector2 ( 156 , 156 )
            portrait . expand_mode = TextureRect . EXPAND_IGNORE_SIZE
            portrait . stretch_mode = TextureRect . STRETCH_KEEP_ASPECT_CENTERED
            portrait . mouse_filter = Control . MOUSE_FILTER_IGNORE
            portrait_row . add_child ( portrait )
            var captions : VBoxContainer = VBoxContainer . new ( )
            captions . size_flags_horizontal = Control . SIZE_EXPAND_FILL
            captions . alignment = BoxContainer . ALIGNMENT_CENTER
            portrait_row . add_child ( captions )
            captions . add_child ( _label ( _server_text ( definition . get ( "name" , id ) ) , 31 ) )
            captions . add_child ( _label ( _server_text ( definition . get ( "weapon_name" , "" ) ) , 22 , "a5d5ac" ) )
            _art_panel ( card , str ( definition . get ( "colony_art" , "races/" + id + "/colony" ) ) , 220 )
            card . add_child ( _label ( _server_text ( definition . get ( "description" , "" ) ) , 22 , "c9d9cb" ) )
            card . add_child ( _label ( I18n . t ( "Przewaga: " ) + _server_text ( definition . get ( "trait" , "" ) ) , 22 , "a5d5ac" ) )
            card . add_child ( _label ( I18n . t ( "Ograniczenie: " ) + _server_text ( definition . get ( "tradeoff" , "" ) ) , 22 , "e6b774" ) )
            card . add_child ( _label ( I18n . t ( "Stały wybór dla tego imperium" ) , 22 , "a0b3a4" ) )
            var button : Button = _button ( I18n . t ( "Wybieram: " ) + _server_text ( definition . get ( "name" , id ) ) , _choose_race . bind ( id ) , true )
            button . name = "ChooseRace_" + id
            button . custom_minimum_size . y = 88
            card . add_child ( button )
            race_buttons [ id ] = button
    _refresh_race_controls ( )


func _refresh_race_controls ( ) -> void :
    if not is_instance_valid ( race_status ) :
        return
    var allowed : bool = bool ( state . get ( "race_choice_allowed" , false ) )
    var pending_choice : bool = str ( uncertain_action . get ( "type" , "" ) ) == "choose_race"
    for button : Button in race_buttons . values ( ) :
        button . disabled = session_token . is_empty ( ) or request_pending or not uncertain_action . is_empty ( ) or not allowed or update_required
    race_retry_button . disabled = request_pending or update_required
    race_logout_button . disabled = request_pending or update_required
    if pending_choice :
        race_status . text = I18n . t ( "Potwierdzanie wyboru rasy…" )
        if not race_error_message . is_empty ( ) :
            race_status . text = race_error_message + I18n . t ( "\nWybierz Odśwież, aby sprawdzić ten sam wybór." )
        race_status . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ff9287" ) ) if not race_error_message . is_empty ( ) else _ui_color ( Color ( "e6b774" ) ) )
    elif not allowed and _needs_race_choice ( ) :
        race_status . text = _server_text ( state . get ( "race_choice_reason" , I18n . t ( "Poczekaj na zakończenie projektów i powrót flot, następnie odśwież." ) ) )
        race_status . add_theme_color_override ( "font_color" , _ui_color ( Color ( "e6b774" ) ) )
    elif allowed and race_error_message . is_empty ( ) :
        race_status . text = I18n . t ( "Wybierz rasę, aby rozpocząć rozwój kolonii." )
        race_status . add_theme_color_override ( "font_color" , _ui_color ( Color ( "a5d5ac" ) ) )


func _choose_race ( id : String ) -> void :
    if session_token . is_empty ( ) or showing_login or update_required or not _needs_race_choice ( ) :
        return
    if request_pending or not uncertain_action . is_empty ( ) :
        _notify ( I18n . t ( "Poczekaj na potwierdzenie serwera lub wybierz Odśwież." ) , true )
        return
    if not bool ( state . get ( "race_choice_allowed" , false ) ) :
        _refresh_race_controls ( )
        return
    if not race_buttons . has ( id ) :
        return
    race_error_message = ""
    _request ( "/api/action" , { "type" : "choose_race" , "race_id" : id , "planet_id" : selected_planet , "request_id" : _new_request_id ( ) } , "action" )


func _refresh_race_identity ( ) -> void :
    var definition : Dictionary = _selected_race ( )
    race_identity . hide ( )
    biome_toggle . hide ( )
    colony_panorama . show ( )
    if definition . is_empty ( ) :
        race_portrait . texture = null
        race_colony . texture = null
        return
    race_name . text = _server_text ( definition . get ( "name" , "" ) )
    race_trait . text = _server_text ( definition . get ( "trait" , "" ) )
    race_weapon . text = I18n . t ( "Uzbrojenie: " ) + _server_text ( definition . get ( "weapon_name" , "" ) )
    race_portrait . texture = ArtLibrary . texture ( str ( definition . get ( "portrait_art" , "" ) ) )
    race_colony . texture = ArtLibrary . texture ( str ( definition . get ( "colony_art" , "" ) ) )


func _toggle_biome_view ( ) -> void :
    biome_expanded = true
    _refresh_race_identity ( )


func _catalog_entry ( key : String , group : String = "" ) -> Dictionary :
    var groups : Array [ String ] = [ "buildings" , "research" , "ships" , "defenses" ]
    if not group . is_empty ( ) :
        groups . clear ( )
        groups . append ( group )
    for catalog_group : String in groups :
        for entry : Dictionary in state . get ( "catalog" , { } ) . get ( catalog_group , [ ] ) :
            if str ( entry . get ( "key" , "" ) ) == key :
                return entry
    return { }


func _catalog_name ( key : String , group : String = "" ) -> String :
    return _server_text ( _catalog_entry ( key , group ) . get ( "name" , I18n . t ( str ( NAMES . get ( key , key ) ) ) ) )


func _entry_art_key ( entry : Dictionary , fallback : String ) -> String :
    return ArtLibrary . catalog_art_key ( entry , fallback , str ( state . get ( "player" , { } ) . get ( "race_id" , "" ) ) )


func _catalog_texture ( key : String , group : String = "" ) -> Texture2D :
    return ArtLibrary . texture ( _entry_art_key ( _catalog_entry ( key , group ) , key ) )


func _make_planet_tab ( body : VBoxContainer ) -> void :
    var identity : VBoxContainer = _card ( body )
    race_identity = identity . get_parent ( ) as Control
    race_identity . name = "RaceIdentity"
    race_identity . visible = false
    var architecture : Control = _art_panel ( identity , "" , 220 )
    race_colony = architecture . get_node ( "Illustration" ) as TextureRect
    var identity_row : HBoxContainer = _row ( _art_caption ( architecture ) )
    race_portrait = TextureRect . new ( )
    race_portrait . custom_minimum_size = Vector2 ( 88 , 88 )
    race_portrait . expand_mode = TextureRect . EXPAND_IGNORE_SIZE
    race_portrait . stretch_mode = TextureRect . STRETCH_KEEP_ASPECT_CENTERED
    race_portrait . mouse_filter = Control . MOUSE_FILTER_IGNORE
    identity_row . add_child ( race_portrait )
    race_name = _label ( "" , 30 )
    race_name . size_flags_vertical = Control . SIZE_SHRINK_CENTER
    identity_row . add_child ( race_name )
    race_trait = _label ( "" , 22 , "c9d9cb" )
    identity . add_child ( race_trait )
    race_weapon = _label ( "" , 22 , "a5d5ac" )
    identity . add_child ( race_weapon )
    biome_toggle = _button ( I18n . t ( "Krajobraz planety" ) , _toggle_biome_view )
    biome_toggle . custom_minimum_size . y = 64
    biome_toggle . visible = false
    body . add_child ( biome_toggle )
    var panorama : Control = _art_panel ( body , "worlds/colony_" + ArtLibrary . planet_variant ( selected_planet ) , 310 )
    panorama . name = "ColonyPanorama"
    colony_panorama = panorama
    colony_illustration = panorama . get_node ( "Illustration" ) as TextureRect
    var title_group : VBoxContainer = _art_caption ( panorama )
    title_group . add_child ( _label ( I18n . t ( "TWOJA KOLONIA" ) , 22 , "a5d5ac" ) )
    planet_title = _label ( I18n . t ( "Kolonia" ) , 36 )
    title_group . add_child ( planet_title )
    planet_subtitle = _label ( I18n . t ( "Imperium" ) , 22 , "c8ddcb" )
    title_group . add_child ( planet_subtitle )
    var stats : HBoxContainer = _row ( _card ( body ) )
    var energy : VBoxContainer = VBoxContainer . new ( )
    energy . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    stats . add_child ( energy )
    var energy_row : HBoxContainer = _row ( energy )
    energy_row . add_child ( _icon ( "energy" , 28 ) )
    energy_label = _label ( I18n . t ( "Energia" ) , 22 , "ffc56f" )
    energy_row . add_child ( energy_label )
    energy_bar = _meter ( "ffc56f" )
    energy . add_child ( energy_bar )
    production_label = _label ( I18n . t ( "Wydobycie 100%" ) , 22 , "a0b3a4" )
    energy . add_child ( production_label )
    var shield : VBoxContainer = VBoxContainer . new ( )
    shield . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    stats . add_child ( shield )
    var shield_row : HBoxContainer = _row ( shield )
    shield_row . add_child ( _icon ( "shield" , 28 ) )
    shield_row . add_child ( _label ( I18n . t ( "Ochrona" ) , 22 , "a0b3a4" ) )
    protection_label = _label ( "—" , 22 , "91c89b" )
    shield . add_child ( protection_label )
    queue_label = _label ( I18n . t ( "Wybierz budynek" ) , 22 )
    var queue : VBoxContainer = _card ( body )
    var queue_row : HBoxContainer = _row ( queue )
    queue_art = _icon ( "time" , 38 )
    queue_row . add_child ( queue_art )
    queue_row . add_child ( queue_label )
    queue_bar = _meter ( "91c89b" )
    queue . add_child ( queue_bar )
    building_heading = _label ( I18n . t ( "Rozbudowa kolonii" ) , 28 )
    body . add_child ( building_heading )
    building_heading . hide ( )
    building_carousel = CatalogCarouselScript . new ( )
    body . add_child ( building_carousel )
    building_carousel . setup ( self , "build" )
    building_list = building_carousel . cards
    building_list . name = "ColonyInfrastructure"

    unique_building_section = VBoxContainer . new ( )
    unique_building_section . name = "UniqueRaceBuildings"
    unique_building_section . visible = false
    body . add_child ( unique_building_section )
    unique_building_heading = _label ( I18n . t ( "Budynki rasy" ) , 28 )
    unique_building_section . add_child ( unique_building_heading )
    unique_building_list = VBoxContainer . new ( )
    unique_building_list . name = "UniqueBuildingCards"
    unique_building_section . add_child ( unique_building_list )
    inactive_racial_section = VBoxContainer . new ( )
    inactive_racial_section . name = "InactiveRacialBuildings"
    inactive_racial_section . hide ( )
    body . add_child ( inactive_racial_section )


func _make_galaxy_tab ( body : VBoxContainer ) -> void :
    var heading : HBoxContainer = _row ( body )
    heading . add_child ( _label ( I18n . t ( "Galaktyka" ) , 30 ) )
    galaxy_toggle = _button ( I18n . t ( "Układ" ) , _toggle_galaxy_overview )
    galaxy_toggle . custom_minimum_size = Vector2 ( 136 , 64 )
    galaxy_toggle . size_flags_horizontal = Control . SIZE_SHRINK_END
    heading . add_child ( galaxy_toggle )
    var galaxy_bar : HBoxContainer = _row ( body )
    galaxy_bar . name = "GalaxySelectorBar"
    previous_galaxy_button = _button ( "‹" , _step_galaxy . bind ( -1 ) )
    previous_galaxy_button . name = "PreviousGalaxy"
    previous_galaxy_button . custom_minimum_size = Vector2 ( 58 , 76 )
    previous_galaxy_button . size_flags_horizontal = Control . SIZE_SHRINK_BEGIN
    previous_galaxy_button . tooltip_text = I18n . t ( "Poprzednia galaktyka" )
    galaxy_bar . add_child ( previous_galaxy_button )
    galaxy_picker = _choice ( I18n . t ( "Wybierz galaktykę" ) , 76 )
    galaxy_picker . name = "GalaxyPicker"
    galaxy_picker . item_selected . connect ( _select_galaxy )
    galaxy_bar . add_child ( galaxy_picker )
    next_galaxy_button = _button ( "›" , _step_galaxy . bind ( 1 ) )
    next_galaxy_button . name = "NextGalaxy"
    next_galaxy_button . custom_minimum_size = Vector2 ( 58 , 76 )
    next_galaxy_button . size_flags_horizontal = Control . SIZE_SHRINK_END
    next_galaxy_button . tooltip_text = I18n . t ( "Następna galaktyka" )
    galaxy_bar . add_child ( next_galaxy_button )
    galaxy_summary = _label ( "" , 22 , "c9d9cb" )
    body . add_child ( galaxy_summary )
    galaxy_travel_note = _label ( "" , 21 , "ffc56f" )
    body . add_child ( galaxy_travel_note )
    galaxy_overview = VBoxContainer . new ( )
    galaxy_overview . visible = true
    body . add_child ( galaxy_overview )
    var legend : HFlowContainer = HFlowContainer . new ( )
    legend . add_theme_constant_override ( "h_separation" , 18 )
    galaxy_overview . add_child ( legend )
    for marker : Array in [ [ I18n . t ( "● Twoje" ) , "91c89b" ] , [ I18n . t ( "● Gracze" ) , "ffc56f" ] , [ I18n . t ( "● Rój" ) , "ff827a" ] , [ I18n . t ( "○ Wolne" ) , "aabdaf" ] ] :
        var caption : Label = _token_label ( marker [ 0 ] , 22 , marker [ 1 ] )
        legend . add_child ( caption )
    galaxy_map = GalaxyMapScript . new ( )
    galaxy_map . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    galaxy_overview . add_child ( galaxy_map )
    galaxy_map . custom_minimum_size . y = 640
    galaxy_map . connect ( "system_selected" , _system_from_overview )
    var flight_legend: HFlowContainer = HFlowContainer.new()
    flight_legend.add_theme_constant_override("h_separation", 16)
    galaxy_overview.add_child(flight_legend)
    flight_legend.name = "FleetMapLegend"
    for entry: Array in [["Zwiad", "scout"], ["Transport", "transport"], ["Kolonizacja", "colonize"], ["Atak", "attack"], ["Powrót", "returning"], ["Ekspedycja", "expedition"]]:
        var fleet: Dictionary = {"mission": entry[1], "status": entry[1]}
        flight_legend.add_child(_token_label("▶ " + I18n.t(str(entry[0])), 18, GalaxyMapScript.fleet_color(fleet).to_html(false)))
    var tools_row : HBoxContainer = _row ( galaxy_overview )
    tools_row . add_child ( _button ( "−" , func ( ) -> void : galaxy_map . call ( "zoom_out" ) ) )
    tools_row . add_child ( _button ( "+" , func ( ) -> void : galaxy_map . call ( "zoom_in" ) ) )
    tools_row . add_child ( _button ( I18n . t ( "Całość" ) , func ( ) -> void : galaxy_map . call ( "reset_view" ) ) )
    tools_row . add_child ( _button ( I18n . t ( "Moja" ) , _focus_home_system ) )
    var system_bar : HBoxContainer = _row ( body )
    var previous : Button = _button ( "‹" , _step_system . bind ( -1 ) )
    previous . custom_minimum_size = Vector2 ( 64 , 72 )
    previous . size_flags_horizontal = Control . SIZE_SHRINK_BEGIN
    system_bar . add_child ( previous )
    system_picker = _choice ( I18n . t ( "Wybierz układ" ) , 72 )
    system_picker . item_selected . connect ( func ( index : int ) -> void : _choose_system ( str ( system_picker . get_item_metadata ( index ) ) ) )
    system_bar . add_child ( system_picker )
    var next : Button = _button ( "›" , _step_system . bind ( 1 ) )
    next . custom_minimum_size = Vector2 ( 64 , 72 )
    next . size_flags_horizontal = Control . SIZE_SHRINK_END
    system_bar . add_child ( next )
    system_heading = _label ( I18n . t ( "Układ planetarny" ) , 27 )
    body . add_child ( system_heading )
    system_coordinates = _label ( "" , 22 , "a0b3a4" )
    body . add_child ( system_coordinates )
    planet_list = VBoxContainer . new ( )
    body . add_child ( planet_list )


func _toggle_galaxy_overview ( ) -> void :
    galaxy_overview . visible = not galaxy_overview . visible
    galaxy_toggle . text = I18n . t ( "Układ" ) if galaxy_overview . visible else I18n . t ( "Mapa" )
    if galaxy_overview . visible :
        _show_full_galaxy_map ( )
    elif compact_ui != null :
        compact_ui . sync_galaxy ( )


func _show_full_galaxy_map ( focus_colony : bool = true ) -> void :
    galaxy_overview . visible = true
    galaxy_toggle . text = I18n . t ( "Układ" )
    galaxy_map . call ( "reset_view" )
    var focused : Control = get_viewport ( ) . gui_get_focus_owner ( )
    if focused != null and tabs [ 1 ] . is_ancestor_of ( focused ) :
        focused . release_focus ( )
    tabs [ 1 ] . scroll_vertical = 0
    tabs [ 1 ] . set_deferred ( "scroll_vertical" , 0 )

    if compact_ui != null :
        compact_ui . sync_galaxy ( )
    if focus_colony :
        _focus_home_system ( )
    elif not selected_system . is_empty ( ) :
        galaxy_map . call ( "focus_system" , selected_system , GalaxyMapScript . DEFAULT_FOCUS_ZOOM )


func _open_galaxy_map ( ) -> void :

    _open_tab ( 1 )
    if planetary_ui != null and planetary_ui . open_first_galaxy_visit ( ) :
        return
    _show_full_galaxy_map ( )


func _step_galaxy ( direction : int ) -> void :
    if galaxy_picker . item_count < 2 :
        return
    _select_galaxy ( posmod ( galaxy_picker . selected + direction , galaxy_picker . item_count ) )


func _system_from_overview ( id : String ) -> void :
    _choose_system ( id )
    galaxy_overview . visible = false
    galaxy_toggle . text = I18n . t ( "Mapa" )
    tabs [ 1 ] . scroll_vertical = 0

    if compact_ui != null :
        compact_ui . sync_galaxy ( )


func _step_system ( direction : int ) -> void :
    if system_picker . item_count == 0 :
        return
    var index : int = posmod ( system_picker . selected + direction , system_picker . item_count )
    _choose_system ( str ( system_picker . get_item_metadata ( index ) ) )


func _focus_home_system ( ) -> void :
    var location : Dictionary = GalaxyGuidanceModel . home_location ( state , selected_planet )
    if location . is_empty ( ) :
        return
    selected_galaxy = str ( location [ "system" ] . get ( "galaxy_id" , "g1" ) )
    _choose_system ( str ( location [ "system" ] . get ( "id" , "" ) ) )
    galaxy_map . call ( "focus_system" , selected_system , GalaxyMapScript . DEFAULT_FOCUS_ZOOM )


func _make_fleet_tab ( body : VBoxContainer ) -> void :

    fleet_mode_bar = PanelContainer . new ( )
    fleet_mode_bar . name = "FleetModeSwitch"
    fleet_mode_bar . set_anchors_and_offsets_preset ( Control . PRESET_TOP_WIDE )
    fleet_mode_bar . offset_bottom = 78
    fleet_mode_bar . resized . connect ( _fit_fleet_mode_bar )
    fleet_mode_bar . add_theme_stylebox_override ( "panel" , _style ( "08110d" , "08110d" , 0 , 0 ) )
    tabs [ 2 ] . get_parent ( ) . add_child ( fleet_mode_bar )
    var modes : HBoxContainer = _row ( fleet_mode_bar )
    for index : int in range ( 2 ) :
        var mode_button : Button = _button ( [ I18n . t ( "Nowa misja" ) , I18n . t ( "Budowa" ) ] [ index ] , _fleet_primary_navigation if index == 0 else _toggle_fleet_construction )
        mode_button . name = "FleetMissionsTab" if index == 0 else "FleetConstructionTab"
        mode_button . toggle_mode = true
        mode_button . custom_minimum_size . y = 72
        mode_button . autowrap_mode = TextServer . AUTOWRAP_OFF
        mode_button . size_flags_vertical = Control . SIZE_SHRINK_CENTER
        mode_button . add_theme_font_size_override ( "font_size" , 22 )
        modes . add_child ( mode_button )
        fleet_mode_buttons . append ( mode_button )
    fleet_active_button = _active_missions_shortcut ( )
    fleet_active_button . name = "ActiveMissionsShortcut"
    fleet_active_button . autowrap_mode = TextServer . AUTOWRAP_OFF
    fleet_active_button . size_flags_vertical = Control . SIZE_SHRINK_CENTER
    modes . add_child ( fleet_active_button )
    tabs [ 2 ] . offset_top = 90
    body . size_flags_vertical = Control . SIZE_EXPAND_FILL
    var fleet_art : Control = _art_panel ( body , "shipyard" , 230 )
    fleet_header_art = fleet_art . get_node ( "Illustration" ) as TextureRect
    _art_caption ( fleet_art ) . add_child ( _label ( I18n . t ( "Dowództwo floty" ) , 32 ) )
    fleet_missions_view = VBoxContainer . new ( )
    fleet_missions_view . name = "FleetMissions"
    body . add_child ( fleet_missions_view )
    fleet_build_view = VBoxContainer . new ( )
    fleet_build_view . name = "FleetConstruction"
    fleet_build_view . size_flags_vertical = Control . SIZE_EXPAND_FILL
    body . add_child ( fleet_build_view )
    var form : VBoxContainer = _card ( fleet_missions_view )
    form . add_child ( _label ( I18n . t ( "NOWA MISJA" ) , 17 , "91c89b" ) )
    form . add_child ( _label ( I18n . t ( "Cel ekspedycji" ) , 21 ) )
    target_picker = _choice ( I18n . t ( "Cel ekspedycji" ) , 88 )
    target_picker . item_selected . connect ( _select_target )
    form . add_child ( target_picker )
    target_label = _label ( I18n . t ( "Wybierz planetę na mapie lub z listy." ) , 19 , "a0b3a4" )
    form . add_child ( target_label )
    mission_picker = _choice ( I18n . t ( "Wybierz misję" ) , 88 )
    for caption : String in MISSION_NAMES :
        mission_picker . add_item ( I18n . t ( caption ) )
    mission_picker . item_selected . connect ( _mission_changed )
    form . add_child ( mission_picker )
    mission_hint = _label ( I18n . t ( "Zwiad ujawnia zasoby, flotę i rozwój planety." ) , 20 , "a0b3a4" )
    form . add_child ( mission_hint )
    megastructure_ui . make_fleet_controls ( form )
    fleet_selection_list = VBoxContainer . new ( )
    fleet_selection_list . name = "FleetShipSelection"
    fleet_selection_list . add_theme_constant_override ( "separation" , 16 )
    form . add_child ( fleet_selection_list )
    _refresh_fleet_inputs ( )
    cargo_box = VBoxContainer . new ( )
    cargo_box . visible = false
    form . add_child ( cargo_box )
    cargo_box . add_child ( _label ( I18n . t ( "ŁADUNEK" ) , 17 , "ffc56f" ) )
    for key : String in RESOURCE_KEYS :
        var row : HBoxContainer = _row ( cargo_box )
        row . add_child ( _icon ( key , 28 ) )
        row . add_child ( _label ( I18n . t ( str ( RESOURCE_NAMES [ key ] ) ) , 19 ) )
        var amount : MobileQuantityScript = _spin ( 0 , 999999 )
        amount . value_changed . connect ( _fleet_value_changed )
        cargo_box . add_child ( amount )
        cargo_inputs [ key ] = amount
    var dock_body : VBoxContainer = VBoxContainer . new ( )
    dock_body . add_theme_constant_override ( "separation" , 6 )
    fleet_action_bar . add_child ( dock_body )
    quote_label = _label ( I18n . t ( "Wybierz statki i sprawdź trasę przed startem." ) , 19 , "a0b3a4" )
    dock_body . add_child ( quote_label )
    var dock_buttons : HBoxContainer = _row ( dock_body )
    preview_button = _button ( I18n . t ( "Sprawdź trasę" ) , _preview_fleet )
    preview_button . name = "CheckRoute"
    preview_button . custom_minimum_size . y = 68
    preview_button . add_theme_font_size_override ( "font_size" , 22 )
    dock_buttons . add_child ( preview_button )
    send_button = _button ( I18n . t ( "Wyślij flotę" ) , _send_fleet , true )
    send_button . disabled = true
    send_button . name = "SendFleet"
    send_button . custom_minimum_size . y = 68
    send_button . add_theme_font_size_override ( "font_size" , 22 )
    dock_buttons . add_child ( send_button )
    fleet_missions_view . add_child ( _label ( I18n . t ( "Trwające misje" ) , 27 ) )
    fleet_list = VBoxContainer . new ( )
    fleet_missions_view . add_child ( fleet_list )
    shipyard_heading = _label ( I18n . t ( "Stocznia" ) , 27 )
    fleet_build_view . add_child ( shipyard_heading )
    shipyard_heading . hide ( )
    ship_carousel = CatalogCarouselScript . new ( )
    fleet_build_view . add_child ( ship_carousel )
    ship_carousel . setup ( self , "ship" )
    ship_list = ship_carousel . cards
    defense_section = VBoxContainer . new ( )
    defense_section . name = "PlanetaryDefense"
    fleet_build_view . add_child ( defense_section )
    defense_section . size_flags_vertical = Control . SIZE_EXPAND_FILL
    defense_carousel = CatalogCarouselScript . new ( )
    defense_section . add_child ( defense_carousel )
    defense_carousel . setup ( self , "defense" )
    defense_list = defense_carousel . cards
    _set_fleet_mode ( 1 )
    _fit_fleet_mode_bar . call_deferred ( )


func _fit_fleet_mode_bar ( ) -> void :
    if not is_instance_valid ( fleet_mode_bar ) or tabs . size ( ) <= 2 :
        return


    # Keep this one-line toolbar independent of transient wrapped-text minimums.
    var height : float = 78.0
    if absf ( fleet_mode_bar . offset_bottom - height ) > 0.5 :
        fleet_mode_bar . offset_bottom = height
    var content_top : float = height + 12.0
    if absf ( tabs [ 2 ] . offset_top - content_top ) > 0.5 :
        tabs [ 2 ] . offset_top = content_top


func _active_missions_shortcut ( height : float = 72.0 ) -> Button :
    var button : Button = _button ( I18n . t ( "Trwające misje" ) , _open_active_missions , true )
    button . icon = _texture ( "fleet" )
    button . expand_icon = true
    button . add_theme_constant_override ( "icon_max_width" , 28 )
    button . add_theme_font_size_override ( "font_size" , 20 )
    button . custom_minimum_size . y = height

    button . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    return button


func _selectable_ship_keys ( ) -> Array [ String ] :
    var keys : Array [ String ] = [ ]
    var catalog : Dictionary = state . get ( "catalog" , { } )
    if not catalog . has ( "ships" ) :

        return SHIP_KEYS . duplicate ( )
    for entry : Dictionary in catalog . get ( "ships" , [ ] ) :
        var key : String = str ( entry . get ( "key" , "" ) )
        if not key . is_empty ( ) and not key in keys :
            keys . append ( key )
    return keys


func _refresh_fleet_inputs ( ) -> void :
    if fleet_selection_list == null :
        return
    var keys : Array [ String ] = _selectable_ship_keys ( )
    for obsolete : String in fleet_selection_rows . keys ( ) :
        if obsolete in keys :
            continue
        var old_row : Control = fleet_selection_rows [ obsolete ]
        old_row . get_parent ( ) . remove_child ( old_row )
        old_row . queue_free ( )
        fleet_selection_rows . erase ( obsolete )
        fleet_inputs . erase ( obsolete )
        fleet_names . erase ( obsolete )
        fleet_portraits . erase ( obsolete )
        fleet_available . erase ( obsolete )
        fleet_descriptions . erase ( obsolete )
    for index : int in range ( keys . size ( ) ) :
        var key : String = keys [ index ]
        if not fleet_selection_rows . has ( key ) :
            var selection : VBoxContainer = VBoxContainer . new ( )
            selection . name = "FleetSelection_" + key
            selection . add_theme_constant_override ( "separation" , 8 )
            fleet_selection_list . add_child ( selection )
            fleet_selection_rows [ key ] = selection
            var row : HBoxContainer = _row ( selection )
            var portrait : TextureRect = TextureRect . new ( )
            portrait . custom_minimum_size = Vector2 ( 108 , 80 )
            portrait . expand_mode = TextureRect . EXPAND_IGNORE_SIZE
            portrait . stretch_mode = TextureRect . STRETCH_KEEP_ASPECT_CENTERED
            portrait . size_flags_vertical = Control . SIZE_SHRINK_CENTER
            portrait . mouse_filter = Control . MOUSE_FILTER_IGNORE
            row . add_child ( portrait )
            var caption : VBoxContainer = VBoxContainer . new ( )
            caption . size_flags_horizontal = Control . SIZE_EXPAND_FILL
            row . add_child ( caption )
            var ship_name : Label = _label ( _catalog_name ( key , "ships" ) , 22 )
            caption . add_child ( ship_name )
            fleet_names [ key ] = ship_name
            var ship_description : Label = _label ( "" , 19 , "a5d5ac" )
            ship_description . name = "FleetShipDescription"
            caption . add_child ( ship_description )
            fleet_descriptions [ key ] = ship_description
            fleet_portraits [ key ] = portrait
            var available : Label = _label ( I18n . t ( "Dostępne: 0" ) , 22 , "ffffff" )
            caption . add_child ( available )
            fleet_available [ key ] = available
            var amount : MobileQuantityScript = _spin ( 0 , 9999 )
            amount . value_changed . connect ( _fleet_value_changed )
            selection . add_child ( amount )
            fleet_inputs [ key ] = amount
        fleet_selection_list . move_child ( fleet_selection_rows [ key ] , index )
        var count : int = int ( state . get ( "ships" , { } ) . get ( key , 0 ) )
        fleet_names [ key ] . text = _catalog_name ( key , "ships" )
        var ship_description : Label = fleet_descriptions [ key ]
        ship_description . text = CatalogDetailsScript . brief_description ( self , _catalog_entry ( key , "ships" ) )
        ship_description . visible = not ship_description . text . is_empty ( )
        var portrait : TextureRect = fleet_portraits [ key ]
        var art_key : String = _entry_art_key ( _catalog_entry ( key , "ships" ) , key )
        if portrait . texture == null or str ( portrait . get_meta ( "catalog_art_key" , "" ) ) != art_key :
            portrait . texture = ArtLibrary . texture ( art_key )
            portrait . set_meta ( "catalog_art_key" , art_key )
        fleet_available [ key ] . text = I18n . t ( "Dostępne: %d" ) % count
        var spin : MobileQuantityScript = fleet_inputs [ key ]
        spin . max_value = maxi ( count , int ( spin . value ) )


func _set_fleet_mode ( mode : int ) -> void :
    fleet_mode = clampi ( mode , 0 , 2 )
    fleet_missions_view . visible = fleet_mode == 0
    fleet_build_view . visible = fleet_mode != 0
    ship_carousel . visible = fleet_mode == 1
    defense_section . visible = fleet_mode == 2
    tabs [ 2 ] . vertical_scroll_mode = ScrollContainer . SCROLL_MODE_AUTO if fleet_mode == 0 else ScrollContainer . SCROLL_MODE_DISABLED
    fleet_mode_buttons [ 1 ] . text = I18n . t ( "Obrona" ) if fleet_mode == 1 else I18n . t ( "Statki" ) if fleet_mode == 2 else I18n . t ( "Budowa" )
    fleet_mode_bar . visible = current_tab == 2
    if is_instance_valid ( fleet_action_bar ) :
        fleet_action_bar . visible = current_tab == 2 and fleet_mode == 0
    for index : int in range ( fleet_mode_buttons . size ( ) ) :
        var selected : bool = ( index == 0 and fleet_mode == 0 ) or ( index == 1 and fleet_mode != 0 )
        var button : Button = fleet_mode_buttons [ index ]
        button . set_pressed_no_signal ( selected )
        button . add_theme_stylebox_override ( "normal" , _style ( "284b33" if selected else "151515" , "91c89b" if selected else "262626" , 13 , 14 ) )
        button . add_theme_stylebox_override ( "pressed" , _style ( "284b33" , "91c89b" , 13 , 14 ) )
        button . add_theme_color_override ( "font_color" , _ui_color ( Color ( "b7e3bd" if selected else "9bb0a0" ) ) )
        button . add_theme_color_override ( "font_pressed_color" , _ui_color ( Color ( "b7e3bd" ) ) )
    var focused : Control = get_viewport ( ) . gui_get_focus_owner ( )
    if focused != null and tabs [ 2 ] . is_ancestor_of ( focused ) :
        focused . release_focus ( )
    tabs [ 2 ] . scroll_vertical = 0
    tabs [ 2 ] . set_deferred ( "scroll_vertical" , 0 )

    if compact_ui != null :
        compact_ui . sync_navigation ( )


func _toggle_fleet_construction ( ) -> void :
    if compact_ui != null :
        compact_ui . close_details ( )
        compact_ui . close_composer ( )
    _set_fleet_mode ( 2 if fleet_mode == 1 else 1 )
    _open_tab ( 2 )
    _reset_page_scroll ( ship_carousel if fleet_mode == 1 else defense_carousel )


func _open_active_missions ( ) -> void :
    if compact_ui != null :
        compact_ui . close_details ( )
        compact_ui . close_composer ( )
    _set_fleet_mode ( 0 )
    _open_tab ( 2 )


func _start_new_mission ( ) -> void :
    if update_required or state . is_empty ( ) :
        return

    selected_target = ""
    selected_scout_system = ""
    preview_requested_fingerprint = ""
    mission_picker . select ( 0 )
    for quantity : Variant in fleet_inputs . values ( ) :
        quantity . value = 0
    for quantity : Variant in cargo_inputs . values ( ) :
        quantity . value = 0
    if megastructure_ui != null and is_instance_valid ( megastructure_ui . travel_mode ) :
        megastructure_ui . travel_mode . set_pressed_no_signal ( false )
    _sync_target ( )
    _mission_changed ( 0 )
    if fleet_navigation != null :
        fleet_navigation . reset_draft ( )
    _open_fleet_missions ( )


func _fleet_primary_navigation ( ) -> void :
    if compact_ui != null and compact_ui . composing and fleet_mode == 0 :
        compact_ui . close_composer ( )
    else :
        _start_new_mission ( )


func _open_fleet_missions ( ) -> void :
    _set_fleet_mode ( 0 )
    _open_tab ( 2 )

    if compact_ui != null :
        compact_ui . open_composer ( )


func _make_research_tab ( body : VBoxContainer ) -> void :
    var skill_card : VBoxContainer = _card ( body )
    skill_entry = skill_card . get_parent ( ) as Control
    skill_entry . name = "SkillWheelEntry"
    skill_entry . visible = false
    skill_card . add_child ( _label ( I18n . t ( "KOŁO UMIEJĘTNOŚCI" ) , 24 , "edc77a" ) )
    skill_entry_summary = _label ( I18n . t ( "Rozwijaj swoją rasę i docieraj do technologii sąsiadów." ) , 22 , "c9d9cb" )
    skill_card . add_child ( skill_entry_summary )
    skill_entry_button = _button ( I18n . t ( "Otwórz koło umiejętności" ) , _open_skill_wheel , true )
    skill_entry_button . custom_minimum_size . y = 88
    skill_card . add_child ( skill_entry_button )
    skill_hunt_button = _button ( I18n . t ( "Znajdź kryształy Roju" ) , _hunt_swarm )
    skill_card . add_child ( skill_hunt_button )
    unique_research_section = VBoxContainer . new ( )
    unique_research_section . name = "UniqueRaceResearch"
    unique_research_section . visible = false
    body . add_child ( unique_research_section )
    unique_research_heading = _label ( I18n . t ( "Badania rasy" ) , 28 )
    unique_research_section . add_child ( unique_research_heading )
    unique_research_list = VBoxContainer . new ( )
    unique_research_list . name = "UniqueResearchCards"
    unique_research_section . add_child ( unique_research_list )
    var research_art : Control = _art_panel ( body , "lab" , 230 )
    research_header_art = research_art . get_node ( "Illustration" ) as TextureRect
    _art_caption ( research_art ) . add_child ( _label ( I18n . t ( "Badania imperium" ) , 32 ) )
    research_list = VBoxContainer . new ( )
    body . add_child ( research_list )
    research_tree_header = VBoxContainer . new ( )
    research_tree_header . visible = false
    body . add_child ( research_tree_header )
    research_tree = ResearchTreeScript . new ( )
    research_tree . setup ( self )
    research_tree . visible = false
    research_tree_scroll = TouchScrollScript . new ( )
    research_tree_scroll . name = "ResearchTreeScroll"
    research_tree_scroll . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    research_tree_scroll . horizontal_scroll_mode = ScrollContainer . SCROLL_MODE_DISABLED
    research_tree_scroll . vertical_scroll_mode = ScrollContainer . SCROLL_MODE_DISABLED
    research_tree_scroll . visible = false
    body . add_child ( research_tree_scroll )
    body . add_child ( research_tree )


func _on_research_layout_toggled ( _enabled : bool ) -> void :

    research_three_rows = true
    _refresh_research_layout ( )


func _refresh_research_layout ( ) -> void :
    var catalog : Array = state . get ( "catalog" , { } ) . get ( "research" , [ ] )
    research_three_rows = true
    research_tree . visible = true
    research_tree_scroll . visible = true
    research_tree_header . hide ( )
    research_list . hide ( )
    unique_research_section . hide ( )
    research_tree . three_rows = true
    if research_tree . get_parent ( ) != research_tree_scroll :
        research_tree . reparent ( research_tree_scroll )
    research_tree_scroll . horizontal_scroll_mode = ScrollContainer . SCROLL_MODE_AUTO
    research_tree_scroll . vertical_scroll_mode = ScrollContainer . SCROLL_MODE_DISABLED
    if tabs . size ( ) > 3 :
        tabs [ 3 ] . vertical_scroll_mode = ScrollContainer . SCROLL_MODE_DISABLED
    research_tree . refresh ( catalog )


func _make_reports_tab ( body : VBoxContainer ) -> void :
    var guide : VBoxContainer = _card ( body )
    onboarding_card = guide . get_parent ( ) as Control
    onboarding_card . name = "FirstStepsCard"
    onboarding_card . visible = false
    var guide_row : HBoxContainer = _row ( guide )
    onboarding_title = _label ( I18n . t ( "Pierwsze kroki" ) , 24 , "a4ef77" )
    guide_row . add_child ( onboarding_title )
    onboarding_button = _button ( I18n . t ( "Przejdź" ) , _open_onboarding_target )
    onboarding_button . custom_minimum_size = Vector2 ( 176 , 64 )
    onboarding_button . add_theme_font_size_override ( "font_size" , 22 )
    onboarding_button . autowrap_mode = TextServer . AUTOWRAP_OFF
    onboarding_button . size_flags_horizontal = Control . SIZE_SHRINK_END
    guide_row . add_child ( onboarding_button )
    onboarding_description = _label ( "" , 21 , "c9d8cb" )
    guide . add_child ( onboarding_description )
    onboarding_progress = _meter ( "91c89b" )
    onboarding_progress . custom_minimum_size . y = 10
    guide . add_child ( onboarding_progress )
    onboarding_skip = _button ( I18n . t ( "Pomiń samouczek" ) , _set_onboarding_skipped . bind ( true ) )
    onboarding_skip . custom_minimum_size . y = 56
    guide . add_child ( onboarding_skip )
    onboarding_resume = _button ( I18n . t ( "Wznów samouczek" ) , _set_onboarding_skipped . bind ( false ) )
    onboarding_resume . custom_minimum_size . y = 56
    onboarding_resume . hide ( )
    body . add_child ( onboarding_resume )
    body . add_child ( _label ( I18n . t ( "Raporty" ) , 30 ) )
    report_list = VBoxContainer . new ( )
    body . add_child ( report_list )


func _spin ( minimum : float , maximum : float ) -> MobileQuantityScript :
    var node : MobileQuantityScript = MobileQuantityScript . new ( )
    node . min_value = minimum
    node . max_value = maximum
    node . step = 1
    node . value = minimum
    node . get_line_edit ( ) . virtual_keyboard_type = LineEdit . KEYBOARD_TYPE_NUMBER
    node . get_line_edit ( ) . select_all_on_focus = true
    return node


func _open_navigation_tab ( index : int ) -> void :


    if index < 0 or index >= tabs . size ( ) :
        return
    if compact_ui != null :
        compact_ui . close_details ( )
    var focused : Control = get_viewport ( ) . gui_get_focus_owner ( )
    if focused != null and tabs [ index ] . is_ancestor_of ( focused ) :
        focused . release_focus ( )
    if index == 1 :
        _open_galaxy_map ( )
    else :
        _open_tab ( index )
        if index == 0 :
            biome_expanded = true
            if is_instance_valid ( colony_panorama ) :
                colony_panorama . show ( )
        elif index == 2 :
            _set_fleet_mode ( 1 )
            if compact_ui != null :
                compact_ui . close_composer ( )
        elif index == 3 and research_tree != null :
            research_tree . selected_key = ""
            research_tree . _update_cards ( )
            research_tree . queue_redraw ( )
    _reset_page_scroll ( tabs [ index ] )


func _reset_page_scroll ( node : Node ) -> void :
    if node is ScrollContainer :
        var scroll : ScrollContainer = node as ScrollContainer
        if scroll . has_method ( "cancel_gesture" ) :
            scroll . call ( "cancel_gesture" )
        scroll . scroll_horizontal = 0
        scroll . scroll_vertical = 0

        scroll . set_deferred ( "scroll_horizontal" , 0 )
        scroll . set_deferred ( "scroll_vertical" , 0 )
    for child : Node in node . get_children ( ) :
        _reset_page_scroll ( child )


func _open_tab ( index : int ) -> void :
    if ranking_ui != null and ranking_ui.visible :
        ranking_ui.close()
    current_tab = index
    if is_instance_valid ( fleet_mode_bar ) :
        fleet_mode_bar . visible = index == 2
    if is_instance_valid ( fleet_action_bar ) :
        fleet_action_bar . visible = index == 2 and fleet_mode == 0
    if index == 4 :
        _mark_reports_read ( )
    for item : int in range ( tabs . size ( ) ) :
        tabs [ item ] . visible = item == index
    for item : int in range ( nav_buttons . size ( ) ) :
        var caption : Label = nav_buttons [ item ] . get_meta ( "caption" ) as Label
        caption . add_theme_color_override ( "font_color" , _ui_color ( Color ( "91c89b" ) ) if item == index else _ui_color ( Color ( "9bb0a0" ) ) )
        nav_buttons [ item ] . add_theme_color_override ( "font_color" , _ui_color ( Color ( "91c89b" ) ) if item == index else _ui_color ( Color ( "9bb0a0" ) ) )
        nav_buttons [ item ] . add_theme_stylebox_override ( "normal" , _style ( "274a33" if item == index else "151515" , "91c89b" if item == index else "262626" , 12 , 6 ) )

    if compact_ui != null :
        compact_ui . sync_navigation ( )


func _guide_target ( kind : String , key : String = "" ) -> void :
    if state . is_empty ( ) or update_required :
        return
    if compact_ui != null :
        compact_ui . close_details ( )
    if kind in [ "reports" , "report" ] :
        _open_tab ( 4 )
        for report : Dictionary in state . get ( "reports" , [ ] ) :
            if not key . is_empty ( ) and str ( report . get ( "id" , "" ) ) == key :
                compact_ui . _open_report ( report . duplicate ( true ) )
                break
        return
    if kind == "missions" :
        _set_fleet_mode ( 0 )
        _open_tab ( 2 )
        compact_ui . close_composer ( )
        for fleet : Dictionary in state . get ( "fleets" , [ ] ) :
            if not key . is_empty ( ) and str ( fleet . get ( "id" , "" ) ) == key :
                compact_ui . _open_fleet_details ( fleet . duplicate ( true ) )
                break
        return
    if kind in [ "galaxy" , "scout" ] :
        if kind == "scout" and not key . is_empty ( ) :
            _prepare_planet_mission ( key , 0 )
        else :
            _open_galaxy_map ( )
            if planetary_ui != null :
                planetary_ui . galaxy_guidance . open_home ( )
        return
    var rows : Dictionary = building_rows
    var tab_index : int = 0
    if kind == "research" :
        _open_tab ( 3 )
        if research_tree != null and research_tree . entries . has ( key ) :
            research_tree . focus_technology ( key )
            return
        rows = research_rows
        tab_index = 3
    elif kind in [ "ship" , "defense" ] :
        _open_tab ( 2 )
        _set_fleet_mode ( 1 if kind == "ship" else 2 )
        rows = ship_rows if kind == "ship" else defense_rows
        tab_index = 2
    else :
        _open_tab ( 0 )
    if not rows . has ( key ) :
        return
    var panel : Control = rows [ key ] [ "panel" ]
    var account : String = str ( state . get ( "player" , { } ) . get ( "id" , "" ) )

    await get_tree ( ) . process_frame
    await get_tree ( ) . process_frame
    if not is_instance_valid ( panel ) or current_tab != tab_index or account != str ( state . get ( "player" , { } ) . get ( "id" , "" ) ) :
        return
    tabs [ tab_index ] . ensure_control_visible ( panel )
    var original : Color = panel . self_modulate
    var tween : Tween = create_tween ( )
    tween . tween_property ( panel , "self_modulate" , Color ( 1.3 , 1.3 , 1.3 , 1.0 ) , 0.18 )
    tween . tween_property ( panel , "self_modulate" , original , 0.65 )


func _authenticate ( register : bool ) -> void :
    if update_required or request_pending :
        return
    if register and google_login != null and google_login . configured and google_login . require_google_registration :
        _start_google_login ( )
        return
    if google_login != null :
        google_login . cancel ( )
    _dismiss_login_keyboard ( )
    var entered_name : String = name_field . text . strip_edges ( )
    if entered_name . is_empty ( ) :
        _set_login_message ( I18n . t ( "Wpisz nazwę imperium." ) , true )
        return
    if entered_name . length ( ) < 3 or entered_name . length ( ) > 20 :
        _set_login_message ( I18n . t ( "Nazwa musi mieć 3–20 znaków: litery, cyfry, spacje, _ lub -." ) , true )
        return
    if password_field . text . length ( ) < 8 or password_field . text . length ( ) > 128 :
        _set_login_message ( I18n . t ( "Hasło musi mieć 8–128 znaków." ) , true )
        return
    if register and password_field . text != repeat_password_field . text :
        _set_login_message ( I18n . t ( "Hasła muszą być identyczne. Wpisz to samo hasło w obu polach." ) , true )
        return
    var connection : Dictionary = ServerAddressScript . parse_input ( server_field . text )
    if connection . has ( "error" ) :
        _set_login_message ( str ( connection [ "error" ] ) , true )
        return
    var prepared_at : int = Time . get_ticks_msec ( )
    _accept_connection ( connection )
    connection_editing = false
    _check_client_version . call_deferred ( )
    session_token = ""
    _reset_world ( )
    _save_session ( )
    _set_login_message ( I18n . t ( "Zakładanie imperium…" ) if register else I18n . t ( "Łączenie…" ) )
    var credentials : Dictionary = { "name" : entered_name , "password" : password_field . text }
    auth_timing_operation = "register" if register else "login"
    auth_timing_prepare_ms = Time . get_ticks_msec ( ) - prepared_at
    auth_timing_request_started = Time . get_ticks_msec ( )
    _request ( "/api/register" if register else "/api/login" , credentials , "auth" )
    if not request_pending :
        AuthTiming . record ( auth_timing_operation , { "prepare_ms" : auth_timing_prepare_ms ,
            "network_ms" : Time . get_ticks_msec ( ) - auth_timing_request_started } , HTTPRequest . RESULT_REQUEST_FAILED )
        auth_timing_operation = ""


func _set_field_text ( field : LineEdit , value : String ) -> void :
    field . set_block_signals ( true )
    field . text = value
    field . set_block_signals ( false )


func _accept_connection ( connection : Dictionary ) -> void :
    var next_url : String = str ( connection [ "url" ] )
    if next_url != server_url :

        session_token = ""
        _reset_world ( )
        _reset_update_origin ( )
    server_url = next_url
    server_override = not baked_server_url . is_empty ( ) and server_url != baked_server_url
    _set_field_text ( server_field , server_url )
    _refresh_connection_hint ( )
    _save_session ( )


func _on_connection_edited ( _text : String ) -> void :
    _cancel_state_request ( )
    if update_required :
        return


    connection_editing = true
    _cancel_update_check ( )
    if request_pending :
        http . cancel_request ( )
        request_pending = false
        request_kind = ""
        auth_timing_operation = ""
    _refresh_login_controls ( )

    _set_login_message ( I18n . t ( "Zaloguj się lub stwórz nowe imperium." ) )


func _use_baked_server ( ) -> void :
    if update_required or baked_server_url . is_empty ( ) :
        return
    _on_connection_edited ( "" )
    _set_field_text ( server_field , baked_server_url )
    _accept_connection ( { "url" : baked_server_url } )
    _set_login_message ( I18n . t ( "Wybrano adres zapisany w aplikacji. Zaloguj się lub utwórz imperium." ) )


func _refresh_connection_hint ( ) -> void :
    default_server_button . visible = not baked_server_url . is_empty ( )
    if server_url . is_empty ( ) :
        connection_hint . text = I18n . t ( "Najpierw wpisz adres serwera w ustawieniach połączenia." )
    elif server_override :
        connection_hint . text = I18n . t ( "Wybrano własny adres serwera. Konto i postęp należą do wybranego świata." )
    elif baked_server_url . is_empty ( ) :
        connection_hint . text = I18n . t ( "Adres serwera został zapamiętany. Zaloguj się lub utwórz imperium." )
    else :
        connection_hint . text = I18n . t ( "Adres serwera jest zapisany w aplikacji. Zaloguj się lub utwórz imperium." )


func _request ( path : String , payload : Dictionary , kind : String , method : int = HTTPClient . METHOD_POST ) -> void :
    if fleet_navigation != null :
        fleet_navigation . refresh . call_deferred ( )
    if update_required :
        return
    if kind in [ "action" , "preview" ] and not requested_planet . is_empty ( ) :
        _notify ( I18n . t ( "Wczytywanie kolonii…" ) )
        return
    if kind == "state" :
        _request_state ( path )
        return
    if request_pending :
        _notify ( I18n . t ( "Trwa łączenie. Spróbuj ponownie za chwilę." ) , true )
        return
    if kind == "action" :
        if not uncertain_action . is_empty ( ) and str ( uncertain_action . get ( "request_id" , "" ) ) != str ( payload . get ( "request_id" , "" ) ) :
            _notify ( I18n . t ( "Poprzedni rozkaz czeka na potwierdzenie. Wybierz „Odśwież”." ) , true )
            return
        uncertain_action = payload . duplicate ( true )

    _cancel_state_request ( )
    request_kind = kind
    command_request_generation += 1
    request_pending = true
    _refresh_onboarding_controls ( )
    _refresh_race_controls ( )
    _refresh_skill_controls ( )
    _refresh_login_controls ( )
    if is_instance_valid ( release_panel ) and kind . begins_with ( "account:" ) :
        release_panel . set_busy ( true )
    var headers : PackedStringArray = PackedStringArray ( [ "Content-Type: application/json" , "Accept: application/json" , "Accept-Language: " + I18n . locale , "X-PGR-Client-Version: " + str ( CLIENT_VERSION_CODE ) ] )
    if not session_token . is_empty ( ) and kind not in [ "auth" , "account:recover" ] :
        headers . append ( "Authorization: Bearer " + session_token )
    command_activity_ticket = player_activity . prepare_request ( path , not session_token . is_empty ( ) and kind == "colony" and method == HTTPClient . METHOD_GET , Time . get_ticks_msec ( ) )
    if command_activity_ticket > 0 :
        headers . append ( "X-AC-Player-Active: 1" )
    var body : String = "" if method == HTTPClient . METHOD_GET else JSON . stringify ( payload )
    var error : Error = http . request ( server_url + path , headers , method , body )
    if error != OK :
        command_activity_ticket = 0
        request_pending = false
        request_kind = ""
        _refresh_login_controls ( )
        _notify ( I18n . t ( "Nie udało się rozpocząć połączenia. " ) + I18n . t ( HOST_OFFLINE_MESSAGE ) , true )
        if kind . begins_with ( "account:" ) :
            _account_error ( I18n . t ( "Nie rozpoczęto połączenia. Wpisz dane i spróbuj ponownie." ) )


func _create_command_request ( ) -> void :
    http = HTTPRequest . new ( )
    http.use_threads = true
    http . timeout = 15.0
    http . max_redirects = 0
    add_child ( http )
    http . request_completed . connect ( _on_response )


func _on_response ( result : int , response_code : int , _headers : PackedStringArray , body : PackedByteArray ) -> void :
    _queue_response_decode("command", command_request_generation, command_activity_ticket, result, response_code, body)


func _consume_command_response(result: int, response_code: int, body: PackedByteArray, decoded: Variant, arrived_msec: int) -> void:
    player_activity . acknowledge ( command_activity_ticket , result == HTTPRequest . RESULT_SUCCESS , response_code , decoded )
    command_activity_ticket = 0
    var received_at : int = arrived_msec
    var timed_operation : String = auth_timing_operation if request_kind == "auth" else ""
    var prepared_ms : int = auth_timing_prepare_ms
    var network_ms : int = received_at - auth_timing_request_started
    if not timed_operation . is_empty ( ) :
        auth_timing_operation = ""
    if fleet_navigation != null :
        fleet_navigation . refresh . call_deferred ( )
    var kind : String = request_kind
    var fleet_action_context : Dictionary = uncertain_action . duplicate ( true ) if kind == "action" else { }
    request_pending = false
    request_kind = ""
    _refresh_login_controls ( )
    _refresh_race_controls . call_deferred ( )
    _refresh_skill_controls . call_deferred ( )
    _refresh_onboarding_controls . call_deferred ( )
    _handle_response ( kind , result , response_code , body , decoded, arrived_msec )
    if kind == "preview" and fleet_navigation != null :
        fleet_navigation . preview_finished ( result , response_code , decoded )
    if fleet_navigation != null and not fleet_action_context . is_empty ( ) :
        fleet_navigation . dispatch_result ( fleet_action_context , result , response_code , decoded )
    if not timed_operation . is_empty ( ) :
        AuthTiming . record ( timed_operation , { "prepare_ms" : prepared_ms , "network_ms" : network_ms ,
            "apply_ms" : Time . get_ticks_msec ( ) - received_at } , result , response_code )


func _handle_response ( kind : String , result : int , response_code : int , body : PackedByteArray , decoded: Variant = null, arrived_msec: int = -1 ) -> void :
    if kind . is_empty ( ) or connection_editing :
        return
    if response_code == 426 :
        if kind . begins_with ( "account:" ) and is_instance_valid ( release_panel ) :
            release_panel . set_busy ( false )
        if kind == "action" :
            uncertain_action . clear ( )
            _invalidate_quote ( )
        var rejected : Variant = decoded if decoded != null else JSON . parse_string ( body . get_string_from_utf8 ( ) )
        _handle_required_update ( rejected . get ( "update" ) if rejected is Dictionary else null )
        return
    if kind . begins_with ( "account:" ) :
        _on_account_response ( kind . trim_prefix ( "account:" ) , result , response_code , body )
        return
    if kind == "logout" :
        return
    if result != HTTPRequest . RESULT_SUCCESS :
        _notify ( I18n . t ( "Brak połączenia. " ) + I18n . t ( HOST_OFFLINE_MESSAGE ) , true )
        if not state . is_empty ( ) :
            _refresh_owned_planets ( )
        return
    if response_code >= 500 :
        _notify ( I18n . t ( "Serwer jest chwilowo niedostępny. " ) + I18n . t ( HOST_OFFLINE_MESSAGE ) , true )
        return
    var parsed : Variant = decoded if decoded != null else JSON.parse_string(body.get_string_from_utf8())
    if not parsed is Dictionary :
        _notify ( I18n . t ( "Nie można połączyć się z galaktyką. Sprawdź adres serwera. " ) + I18n . t ( HOST_OFFLINE_MESSAGE ) , true )
        return
    var response : Dictionary = parsed
    if response_code == 401 and kind != "auth" :
        session_token = ""
        _reset_world ( )
        _save_session ( )
        _set_login_mode ( "login" , false )
        _show_login ( I18n . t ( "Sesja wygasła. Zaloguj się ponownie." ) , true )
        return
    if response_code < 200 or response_code >= 300 or not bool ( response . get ( "ok" , false ) ) :
        if kind == "action" and response_code >= 400 and response_code < 500 :
            uncertain_action . clear ( )
        var error_message : String = _server_text ( response . get ( "error" , I18n . t ( "Nie udało się wykonać polecenia." ) ) ) . strip_edges ( )
        if error_message . is_empty ( ) :
            error_message = I18n . t ( "Nie udało się wykonać polecenia." )
        _notify ( error_message , true )
        if kind == "action" :
            _invalidate_quote ( false )
            quote_label . text = error_message
            quote_label . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ff9287" ) ) )
        if kind == "preview" :
            quote_label . text = error_message
            quote_label . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ff9287" ) ) )
            _invalidate_quote ( false , false )
        return
    if kind == "auth" :
        if str ( response . get ( "token" , "" ) ) . is_empty ( ) or not response . get ( "state" ) is Dictionary :
            _set_login_message ( I18n . t ( "Odpowiedź serwera jest niepełna. Spróbuj ponownie." ) , true )
            return
        if not state . is_empty ( ) :
            _reset_world ( )
        if is_instance_valid ( interaction_guard ) :
            interaction_guard . reset ( )
        deferred_state . clear ( )
        session_token = str ( response . get ( "token" , "" ) )
        password_field . text = ""
        repeat_password_field . text = ""
        _save_session ( )
    if kind == "preview" :
        if preview_requested_fingerprint != _fleet_fingerprint ( ) or preview_requested_world_signature != _quote_world_signature ( state ) or preview_requested_generation != fleet_draft_generation :
            _invalidate_quote ( )
            return
        preview_fingerprint = preview_requested_fingerprint
        quote_ready = bool ( response . get ( "affordable" , true ) )
        send_button . disabled = not quote_ready
        quote_label . text = I18n . t ( "Lot: %s  •  Paliwo: %s\nKoszt zostanie pobrany przy starcie." ) % [ _duration ( float ( response . get ( "seconds" , 0 ) ) ) , _exact_integer ( int ( response . get ( "fuel_cost" , 0 ) ) ) ]
        var route_note : String = _server_text ( response . get ( "message" , "" ) ) . strip_edges ( )
        if not route_note . is_empty ( ) :
            quote_label . text += "\n" + route_note
        var route : Dictionary = response . get ( "route" , { } )
        if bool ( route . get ( "intergalactic" , false ) ) :
            quote_label . text = str ( route . get ( "origin_galaxy_name" , "" ) ) + " → " + str ( route . get ( "target_galaxy_name" , "" ) ) + "\n" + quote_label . text
        if not quote_ready :
            quote_label . text += "\n" + I18n . t ( "Brakujące zasoby: %s" ) % _cost ( response . get ( "shortfall" , { } ) )
            if response . has ( "tunnel" ) :
                quote_label . text += "\n" + I18n . t ( "Brakująca energia: %s" ) % _number ( float ( response [ "tunnel" ] . get ( "energy_shortfall" , 0 ) ) )
        quote_label . add_theme_color_override ( "font_color" , _ui_color ( Color ( "91c89b" ) ) if quote_ready else _ui_color ( Color ( "ff9287" ) ) )
        if fleet_navigation != null :
            fleet_navigation . accept_quote ( response )
        return
    if response . has ( "state" ) and response [ "state" ] is Dictionary :
        if kind == "auth" :

            _apply_state_now ( response [ "state" ] , Time . get_ticks_msec ( ) )
            _set_login_mode ( "" , false )
        else :
            _apply_state ( response [ "state" ], arrived_msec )
    if kind == "action" :
        if compact_ui != null and str ( uncertain_action . get ( "type" , "" ) ) == "fleet" :
            compact_ui . close_composer ( )
        uncertain_action . clear ( )
        _invalidate_quote ( )
        _notify ( _server_text ( response . get ( "message" , I18n . t ( "Polecenie przyjęte." ) ) ) )
    elif kind == "auth" :
        _notify ( I18n . t ( "Witaj, %s." ) % str ( state . get ( "player" , { } ) . get ( "name" , I18n . t ( "dowódco" ) ) ) )
    else :
        _notify ( I18n . t ( "Połączono • świat zapisany na serwerze" ) )


func _request_state ( path : String ) -> void :
    if request_pending or update_required or connection_editing or session_token . is_empty ( ) or not uncertain_action . is_empty ( ) :
        return
    if state_request_pending and state_request_path == path :
        return
    _cancel_state_request ( )
    state_http = HTTPRequest . new ( )
    state_http.use_threads = true
    state_http . timeout = 15.0
    state_http . max_redirects = 0
    add_child ( state_http )
    state_request_path = path
    state_request_pending = true
    state_http . request_completed . connect ( _on_state_response . bind ( state_request_generation ) )
    var headers : PackedStringArray = PackedStringArray ( [ "Accept: application/json" , "Accept-Language: " + I18n . locale , "Authorization: Bearer " + session_token , "X-PGR-Client-Version: " + str ( CLIENT_VERSION_CODE ) ] )
    state_activity_ticket = player_activity . prepare_request ( path , not session_token . is_empty ( ) , Time . get_ticks_msec ( ) )
    if state_activity_ticket > 0 :
        headers . append ( "X-AC-Player-Active: 1" )
    var error : Error = state_http . request ( server_url + path , headers , HTTPClient . METHOD_GET )
    if error != OK :
        _cancel_state_request ( )
        _notify ( I18n . t ( "Nie udało się rozpocząć połączenia. " ) + I18n . t ( HOST_OFFLINE_MESSAGE ) , true )


func _cancel_state_request ( ) -> void :
    state_activity_ticket = 0
    state_request_generation += 1
    state_request_pending = false
    state_request_path = ""
    deferred_state . clear ( )
    if is_instance_valid ( state_http ) :
        state_http . cancel_request ( )
        state_http . queue_free ( )
    state_http = null


func _on_state_response ( result : int , response_code : int , _headers : PackedStringArray , body : PackedByteArray , generation : int ) -> void :
    if generation != state_request_generation :
        return
    _queue_response_decode("state", generation, state_activity_ticket, result, response_code, body)
    if is_instance_valid ( state_http ) :
        state_http . queue_free ( )
    state_http = null


func _queue_response_decode(kind: String, generation: int, ticket: int, result: int, code: int, body: PackedByteArray) -> void:
    var job := ResponseDecodeJob.new()
    job.kind = kind
    job.operation_kind = request_kind
    job.token = session_token
    job.origin = server_url
    job.generation = generation
    job.activity_ticket = ticket
    job.result = result
    job.response_code = code
    job.arrived_msec = Time.get_ticks_msec()
    job.body = body
    # The bound argument retains the packet until the worker finishes, including
    # a logout or a freed UI. The worker never retains the client scene itself.
    job.task_id = WorkerThreadPool.add_task(job.decode.bind(job), false, "Decode game state")
    response_decode_jobs.append(job)


func _finish_response_jobs() -> bool:
    if _ui_interacting():
        return false
    for index: int in range(response_decode_jobs.size() - 1, -1, -1):
        var job: ResponseDecodeJob = response_decode_jobs[index]
        if not WorkerThreadPool.is_task_completed(job.task_id):
            continue
        WorkerThreadPool.wait_for_task_completion(job.task_id)
        response_decode_jobs.remove_at(index)
        if job.kind == "command":
            if job.generation != command_request_generation or not request_pending or job.operation_kind != request_kind or job.token != session_token or job.origin != server_url:
                continue
            _consume_command_response(job.result, job.response_code, job.body, job.decoded, job.arrived_msec)
            return true
        if job.generation != state_request_generation:
            continue
        player_activity.acknowledge(job.activity_ticket, job.result == HTTPRequest.RESULT_SUCCESS, job.response_code, job.decoded)
        state_activity_ticket = 0
        state_request_pending = false
        state_request_path = ""
        if request_pending or update_required or connection_editing or not uncertain_action.is_empty():
            continue
        _handle_response("state", job.result, job.response_code, job.body, job.decoded, job.arrived_msec)
        # Keep a completed state rebuild separate from the periodic UI tick.
        return true
    return false


func _exit_tree() -> void:
    # Reap all pool tasks on teardown. Their callbacks use only retained packets,
    # so waiting here never needs the client scene or a main-thread callback.
    for job: ResponseDecodeJob in response_decode_jobs:
        WorkerThreadPool.wait_for_task_completion(job.task_id)
    response_decode_jobs.clear()


func _ui_interacting ( ) -> bool :
    return is_instance_valid ( interaction_guard ) and interaction_guard . busy ( )


func _defer_ui_refresh(key: String, refresh: Callable) -> bool:
    return is_instance_valid(interaction_guard) and interaction_guard.defer_refresh(key, refresh)


func _flush_deferred_state ( ) -> void :
    if deferred_state . is_empty ( ) or _ui_interacting ( ) or request_pending or update_required or connection_editing :
        return
    var snapshot : Dictionary = deferred_state
    var arrived : int = deferred_state_received_at
    deferred_state = { }
    _apply_state_now ( snapshot , arrived )


func _poll ( force : bool = false ) -> void :
    if not player_activity . foreground :
        return
    if not force and _ui_interacting ( ) :
        return
    if update_required or session_token . is_empty ( ) or request_pending or connection_editing :
        return
    if not uncertain_action . is_empty ( ) :
        _request ( "/api/action" , uncertain_action , "action" )
        return
    if _needs_race_choice ( ) and not force :
        return
    var path : String = "/api/state"
    var planet_id : String = requested_planet if not requested_planet . is_empty ( ) else selected_planet
    if not planet_id . is_empty ( ) :
        path += "?planet_id=" + planet_id . uri_encode ( )
    _request ( path , { } , "colony" if not requested_planet . is_empty ( ) else "state" , HTTPClient . METHOD_GET )


func _retry ( ) -> void :
    if update_required or request_pending :
        return
    if login_screen . visible :
        var connection : Dictionary = ServerAddressScript . parse_input ( server_field . text )
        if connection . has ( "error" ) :
            _show_login ( str ( connection [ "error" ] ) , true )
            return
        _accept_connection ( connection )
    connection_editing = false
    _check_client_version . call_deferred ( )
    if not session_token . is_empty ( ) :
        _poll ( true )
    elif google_login != null and not google_login . is_active ( ) :
        _set_login_message ( I18n . t ( "Łączenie…" ) )
        google_login . load_configuration ( )
    if email_login != null and not email_login . is_active ( ) :
        email_login . load_configuration ( )


func _logout ( ) -> void :
    if update_required :
        return
    if session_token . is_empty ( ) and showing_login :
        if google_login != null :
            google_login . cancel ( )
        if email_login != null :
            email_login . cancel ( )
        _set_login_mode ( "" , false )
        _refresh_google_controls ( )
        return
    var local_started : int = Time . get_ticks_msec ( )
    auth_timing_operation = ""
    var old_token : String = session_token
    var old_origin : String = server_url
    if google_login != null :
        google_login . clear_account_state ( )
    if request_pending :

        request_kind = ""
        request_pending = false
        if http . request_completed . is_connected ( _on_response ) :
            http . request_completed . disconnect ( _on_response )
        http . cancel_request ( )
        http . queue_free ( )
        _create_command_request ( )
    session_token = ""
    _reset_world ( )
    _save_session ( )
    _invalidate_quote ( )
    _set_login_mode ( "login" , false )
    _show_login ( I18n . t ( "Wylogowano. Imperium jest zapisane na serwerze. Możesz ponownie się zalogować." ) )
    _revoke_logged_out_session ( old_origin , old_token )
    AuthTiming . record ( "logout" , { "local_ms" : Time . get_ticks_msec ( ) - local_started } )


func _revoke_logged_out_session ( origin : String , token : String ) -> void :
    if origin . is_empty ( ) or token . is_empty ( ) :
        return
    var revocation : HTTPRequest = SessionRevocationScript . new ( )

    get_tree ( ) . root . add_child ( revocation )
    var headers : PackedStringArray = PackedStringArray ( [
        "Content-Type: application/json" , "Accept: application/json" ,
        "Accept-Language: " + I18n . locale , "X-PGR-Client-Version: " + str ( CLIENT_VERSION_CODE ) ,
        "Authorization: Bearer " + token ,
    ] )
    var error : Error = _request_logout_revocation ( revocation , origin + "/api/logout" , headers )
    if error != OK :
        revocation . queue_free ( )


func _request_logout_revocation ( revocation : HTTPRequest , url : String , headers : PackedStringArray ) -> Error :
    return revocation . request ( url , headers , HTTPClient . METHOD_POST , "{}" )


func _reset_world ( ) -> void :
    if report_notifications != null:
        report_notifications.clear()
    player_activity . reset_account ( )
    command_activity_ticket = 0
    if beginner_guide != null :
        beginner_guide . reset_account ( )
    _cancel_state_request ( )
    if google_login != null :
        google_login . cancel ( )
    if email_login != null :
        email_login . cancel ( )
    if is_instance_valid ( email_reauth_dialog ) :
        email_reauth_dialog . hide ( )
        email_reauth_field . text = ""
    email_entry_open = false
    if is_instance_valid ( email_field ) :
        email_field . text = ""
    if is_instance_valid ( google_reauth_dialog ) :
        google_reauth_dialog . hide ( )
    if communications != null :
        communications . reset ( )
    if ranking_ui != null :
        ranking_ui.reset()
    if alliance_ui != null :
        alliance_ui . reset ( )
    cancel_project_payload . clear ( )
    if is_instance_valid ( cancel_project_dialog ) :
        cancel_project_dialog . hide ( )
    selected_galaxy = "g1"
    galaxy_choices_signature = ""
    if is_instance_valid ( fleet_mode_bar ) :
        _set_fleet_mode ( 1 )
    _close_release_panel ( false )
    report_scope = ""
    report_read_ids . clear ( )
    unread_reports = 0
    incoming_signature = ""
    if is_instance_valid ( incoming_banner ) :
        incoming_banner . visible = false
    if is_instance_valid ( onboarding_card ) :
        onboarding_card . visible = false
    _refresh_report_badge ( )
    _end_skill_navigation ( )
    skill_selected_id = ""
    skill_message = ""
    if is_instance_valid ( skill_overlay ) :
        skill_overlay . visible = false
        skill_wheel . call ( "set_tree" , { } )
    if is_instance_valid ( skill_wallet_button ) :
        skill_wallet_button . visible = false
    state = { }
    if queue_billing != null :
        queue_billing . sign_out ( )
    if planned_queue_ui != null :
        planned_queue_ui . reset ( )
    scout_age_labels . clear ( )
    _apply_race_palette ( "" )
    _clear_race_cards ( )
    race_identity . visible = false
    biome_expanded = false
    biome_toggle . visible = false
    colony_panorama . visible = true
    race_portrait . texture = null
    race_colony . texture = null
    fleet_header_art . texture = null
    research_header_art . texture = null
    for portrait : TextureRect in fleet_portraits . values ( ) :
        portrait . texture = null
    for rows : Dictionary in [ building_rows , ship_rows , research_rows , defense_rows ] :
        for controls : Dictionary in rows . values ( ) :
            controls [ "art" ] . texture = null
    selected_planet = ""
    requested_planet = ""
    selected_system = ""
    selected_target = ""
    selected_scout_system = ""
    own_signature = ""
    galaxy_signature = ""
    system_signature = ""
    reports_signature = ""
    fleets_signature = ""
    uncertain_action . clear ( )
    queue_end = 0.0
    queue_duration = 0.0
    queue_kind = ""
    queue_key = ""
    active_project . visible = false
    fleet_countdowns . clear ( )
    planet_actions . clear ( )
    galaxy_overview . visible = true
    galaxy_toggle . text = I18n . t ( "Układ" )
    galaxy_map . call ( "reset_view" )
    for key : String in fleet_inputs :
        var input : MobileQuantityScript = fleet_inputs [ key ]
        input . value = 0
    for key : String in cargo_inputs :
        var input : MobileQuantityScript = cargo_inputs [ key ]
        input . value = 0
    _invalidate_quote ( )
    _open_tab ( 0 )


func _save_session ( ) -> void :
    var config : ConfigFile = ConfigFile . new ( )
    config . set_value ( "connection" , "url" , server_url )
    config . set_value ( "connection" , "baked_url" , baked_server_url )
    config . set_value ( "connection" , "manual_override" , server_override )
    config . set_value ( "connection" , "token" , session_token )
    config . set_value ( "connection" , "name" , name_field . text . strip_edges ( ) )
    config . save ( session_config_path )


func _load_session ( ) -> void :
    _load_baked_server ( )
    server_url = baked_server_url
    var config : ConfigFile = ConfigFile . new ( )
    if config . load ( session_config_path ) == OK :
        name_field . text = str ( config . get_value ( "connection" , "name" , "" ) )
        var stored : Dictionary = ServerAddressScript . parse_input ( str ( config . get_value ( "connection" , "url" , "" ) ) )
        if not stored . has ( "error" ) :
            var stored_url : String = _migrate_official_server_origin ( str ( stored [ "url" ] ) )
            var stored_baked_url : String = _migrate_official_server_origin ( str ( config . get_value ( "connection" , "baked_url" , "" ) ) )
            var same_build_origin : bool = stored_baked_url == baked_server_url
            var use_override : bool = bool ( config . get_value ( "connection" , "manual_override" , false ) ) and same_build_origin
            if baked_server_url . is_empty ( ) or use_override :
                server_url = stored_url
                server_override = not baked_server_url . is_empty ( ) and server_url != baked_server_url

            if stored_url == server_url :
                session_token = str ( config . get_value ( "connection" , "token" , "" ) )
    _save_session ( )


func _migrate_official_server_origin ( origin : String ) -> String :



    return DEFAULT_SERVER_URL if origin == LEGACY_OFFICIAL_SERVER_URL else origin


func _load_baked_server ( ) -> void :
    if not FileAccess . file_exists ( SERVER_CONFIG_PATH ) :
        server_config_error = I18n . t ( SERVER_CONFIG_ERROR_MESSAGE )
        return
    var file : FileAccess = FileAccess . open ( SERVER_CONFIG_PATH , FileAccess . READ )
    if file == null :
        server_config_error = I18n . t ( SERVER_CONFIG_ERROR_MESSAGE )
        return
    var payload : Variant = JSON . parse_string ( file . get_as_text ( ) )
    file . close ( )
    if not payload is Dictionary or not payload . get ( "server_url" ) is String :
        server_config_error = I18n . t ( SERVER_CONFIG_ERROR_MESSAGE )
        return
    var configured_url : String = str ( payload [ "server_url" ] )
    if configured_url . is_empty ( ) :
        server_config_error = I18n . t ( SERVER_CONFIG_ERROR_MESSAGE )
        return
    var connection : Dictionary = ServerAddressScript . parse_input ( configured_url )
    if connection . has ( "error" ) :
        server_config_error = I18n . t ( SERVER_CONFIG_ERROR_MESSAGE )
        return
    baked_server_url = str ( connection [ "url" ] )


func _show_login ( message : String = "" , error : bool = false ) -> void :
    swarm_hunt_generation += 1
    if ranking_ui != null :
        ranking_ui.reset()
    if alliance_ui != null :
        alliance_ui . reset ( )
    if communications != null :
        communications . close ( )
    _end_skill_navigation ( )
    showing_login = true
    _sync_screen_visibility ( )
    _refresh_login_controls ( )
    if login_announcement != null :
        login_announcement . load_from_server ( )
    if review_prompt != null :
        review_prompt . hide ( )
    if not message . is_empty ( ) :
        _set_login_message ( message , error )


func _notify ( message : String , error : bool = false ) -> void :
    if skill_open and ( error or message != I18n . t ( "Połączono • świat zapisany na serwerze" ) ) :
        skill_message = message
        _refresh_skill_controls ( )
    connection_label . text = message
    connection_label . visible = error or message != I18n . t ( "Połączono • świat zapisany na serwerze" )
    connection_indicator . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ff9287" ) ) if error else _ui_color ( Color ( "91c89b" ) ) )
    connection_label . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ff9287" ) ) if error else _ui_color ( Color ( "91c89b" ) ) )
    if _needs_race_choice ( ) and is_instance_valid ( race_status ) :
        race_error_message = message if error else ""
        race_status . text = message
        race_status . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ff9287" ) ) if error else _ui_color ( Color ( "a5d5ac" ) ) )
        _refresh_race_controls ( )
    if showing_login and ( error or not login_message_error ) :
        _set_login_message ( message , error )


func _apply_state ( next_state : Dictionary, arrived_msec: int = -1 ) -> void :
    var arrived: int = arrived_msec if arrived_msec >= 0 else Time.get_ticks_msec()
    if _ui_interacting ( ) :
        # Parsed response ownership is handed to the client. Deep-copying the
        # entire galaxy here used to stall the very gesture being protected.
        deferred_state = next_state
        deferred_state_received_at = arrived
        return
    deferred_state . clear ( )
    _apply_state_now ( next_state , arrived )


func _apply_state_now ( next_state : Dictionary , arrived_at : int ) -> void :
    refreshing = true
    if not state . is_empty ( ) and _quote_world_signature ( state ) != _quote_world_signature ( next_state ) :
        _invalidate_quote ( )
    var previous_race : String = str ( state . get ( "player" , { } ) . get ( "race_id" , "" ) )
    var previously_choosing : bool = _needs_race_choice ( )
    state = next_state
    if report_notifications != null:
        report_notifications.sync(state)
    ArtLibrary . update_planets ( state )
    var current_race : String = str ( state . get ( "player" , { } ) . get ( "race_id" , "" ) )
    _apply_race_palette ( current_race )
    if current_race != previous_race :
        skill_selected_id = ""
        skill_message = ""
        fleets_signature = ""
        reports_signature = ""
        ArtLibrary . release_other_races ( current_race )
        biome_expanded = false
        if not current_race . is_empty ( ) :
            _open_tab ( 0 )
    _refresh_race_screen ( )
    server_stamp = float ( state . get ( "server_time" , Time . get_unix_time_from_system ( ) ) )
    received_at_msec = arrived_at
    if queue_billing != null :
        queue_billing . apply_server_state ( state )
    var received_planet : String = str ( state . get ( "planet_id" , state . get ( "home_id" , "" ) ) )
    requested_planet = ""
    if selected_planet != received_planet :
        selected_planet = received_planet
        _invalidate_quote ( )
    showing_login = false
    _refresh_google_controls ( )
    if communications != null :
        communications . sync_state ( )
    if alliance_ui != null :
        alliance_ui . sync_state ( )
    _sync_screen_visibility ( )
    if _needs_race_choice ( ) and not previously_choosing :
        DisplayServer . virtual_keyboard_hide ( )
        var focused : Control = get_viewport ( ) . gui_get_focus_owner ( )
        if focused != null :
            focused . release_focus ( )
    _refresh_resource_hud ( )
    _refresh_owned_planets ( )

    colony_illustration . texture = ArtLibrary . colony_texture ( selected_planet )
    var player : Dictionary = state . get ( "player" , { } )
    _refresh_race_identity ( )
    fleet_header_art . texture = _catalog_texture ( "shipyard" , "buildings" )
    research_header_art . texture = _catalog_texture ( "lab" , "buildings" )
    shipyard_heading . text = _catalog_name ( "shipyard" , "buildings" )
    planet_title . text = I18n . t ( "Kolonia" )
    for owned_planet : Dictionary in state . get ( "own_planets" , [ ] ) :
        if str ( owned_planet . get ( "id" , "" ) ) == selected_planet :
            planet_title . text = str ( owned_planet . get ( "name" , I18n . t ( "Kolonia" ) ) )
    planet_subtitle . text = I18n . t ( "%s · Kolonie %d/%d" ) % [ str ( player . get ( "name" , I18n . t ( "Imperium" ) ) ) , state . get ( "own_planets" , [ ] ) . size ( ) , int ( state . get ( "limits" , { } ) . get ( "colonies" , 3 ) ) ]
    var energy : Dictionary = state . get ( "energy" , { } )
    energy_label . text = "%s / %s" % [ _stat_number ( float ( energy . get ( "used" , 0 ) ) ) , _stat_number ( float ( energy . get ( "supply" , 0 ) ) ) ]
    energy_bar . value = minf ( 100.0 , 100.0 * float ( energy . get ( "used" , 0 ) ) / maxf ( 1.0 , float ( energy . get ( "supply" , 0 ) ) ) )
    energy_bar . add_theme_stylebox_override ( "fill" , _style ( "ff9287" if float ( energy . get ( "factor" , 1.0 ) ) < 1.0 else "ffc56f" , "00000000" , 5 , 0 ) )
    production_label . text = I18n . t ( "Produkcja wstrzymana — nieaktywność" ) if PlayerActivityScript . production_paused ( state ) else I18n . t ( "Wydobycie %d%%" ) % roundi ( float ( energy . get ( "factor" , 1.0 ) ) * 100.0 )
    energy_label . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ff9287" ) ) if float ( energy . get ( "factor" , 1.0 ) ) < 1.0 else _ui_color ( Color ( "ffc56f" ) ) )
    var queue : Array = state . get ( "queue" , [ ] )
    queue_end = 0.0
    queue_duration = 0.0
    queue_kind = ""
    queue_key = ""
    queue_art . texture = _texture ( "time" )
    if not queue . is_empty ( ) :
        var task : Dictionary = queue [ 0 ]
        queue_end = float ( task . get ( "ends_at" , 0 ) )
        var task_kind : String = str ( task . get ( "kind" , "build" ) )
        queue_kind = task_kind
        queue_key = str ( task . get ( "key" , "" ) )
        var catalog_group : String = "defenses" if task_kind == "defense" else "ships" if task_kind == "ship" else "research" if task_kind == "research" else "buildings"
        queue_duration = float ( task . get ( "seconds" , 0 ) )
        if queue_duration <= 0 and task . has ( "started_at" ) :
            queue_duration = maxf ( 0.0 , queue_end - float ( task [ "started_at" ] ) )
        if queue_duration <= 0 :


            for entry : Dictionary in state . get ( "catalog" , { } ) . get ( catalog_group , [ ] ) :
                if str ( entry . get ( "key" , "" ) ) == str ( task . get ( "key" , "" ) ) :
                    queue_duration = _catalog_seconds ( entry , int ( task . get ( "amount" , 1 ) ) if task_kind in [ "ship" , "defense" ] else 1 )
        queue_art . texture = _catalog_texture ( queue_key , catalog_group )
        queue_name = _server_text ( task . get ( "name" , _catalog_name ( queue_key , catalog_group ) ) )
        if str ( task . get ( "kind" , "" ) ) in [ "ship" , "defense" ] :
            queue_name += " ×%d" % int ( task . get ( "amount" , 1 ) )
        elif task . has ( "level" ) :
            queue_name += I18n . t ( " · poz. %d" ) % int ( task [ "level" ] )
    var catalog : Dictionary = state . get ( "catalog" , { } )
    _refresh_catalog ( catalog . get ( "buildings" , [ ] ) , building_list , building_rows , "build" )
    _refresh_inactive_racial_buildings ( )
    _refresh_catalog ( catalog . get ( "research" , [ ] ) , research_list , research_rows , "research" )
    _refresh_research_layout ( )
    _refresh_catalog ( catalog . get ( "ships" , [ ] ) , ship_list , ship_rows , "ship" )
    defense_section . visible = fleet_mode == 2
    _refresh_catalog ( catalog . get ( "defenses" , [ ] ) , defense_list , defense_rows , "defense" )
    _refresh_fleet_inputs ( )
    _update_mission_hint ( )
    _refresh_galaxy ( )
    _refresh_fleets ( )
    _refresh_reports ( )
    _refresh_skills ( )
    _refresh_release_state ( )
    _update_clock ( )
    refreshing = false
    _restore_language_view ( )
    if compact_ui != null :
        compact_ui . refresh ( )
    if megastructure_ui != null :
        megastructure_ui . refresh ( )
    if planetary_ui != null :
        planetary_ui . refresh ( )
    if fleet_navigation != null :
        fleet_navigation . refresh ( )
    if planned_queue_ui != null :
        planned_queue_ui . refresh ( )
    if planet_status != null :
        planet_status . refresh ( )
    if beginner_guide != null :
        beginner_guide . refresh ( )
    if review_prompt != null :
        review_prompt . refresh ( state )
    if not str ( state . get ( "selected_planet_lost" , { } ) . get ( "message" , "" ) ) . is_empty ( ) :
        _notify ( str ( state [ "selected_planet_lost" ] [ "message" ] ) , true )


func _refresh_inactive_racial_buildings ( ) -> void :
    if not is_instance_valid ( inactive_racial_section ) :
        return
    var entries : Array = state . get ( "inactive_racial_buildings" , [ ] )
    var signature : String = I18n . locale + JSON . stringify ( entries )
    if signature == inactive_racial_signature :
        return
    inactive_racial_signature = signature
    _clear ( inactive_racial_section )
    inactive_racial_section . hide ( )


    for node : Node in building_list . get_children ( ) :
        if node . has_meta ( "inactive_racial_card" ) :
            building_list . remove_child ( node )
            node . queue_free ( )
    var layout_script : GDScript = preload ( "res://client/scripts/catalog_card_layout.gd" )
    for entry : Dictionary in entries :
        var card : VBoxContainer = _card ( building_list )
        var panel : PanelContainer = card . get_parent ( )
        panel . set_meta ( "inactive_racial_card" , true )
        var layout : Dictionary = layout_script . create ( self , panel , card )
        var content : VBoxContainer = layout [ "content" ]
        var art : Control = _art_panel ( content , _entry_art_key ( entry , str ( entry . get ( "key" , "" ) ) ) , 180 )
        layout_script . fit_art ( panel , art )
        content . add_child ( _label ( str ( entry . get ( "name" , entry . get ( "key" , "" ) ) ) , 28 ) )
        content . add_child ( _label ( str ( entry . get ( "race_name" , "" ) ) + " · " + I18n . t ( "Poziom %d" ) % int ( entry . get ( "level" , 0 ) ) , 22 , "a0b3a4" ) )
        content . add_child ( _label ( I18n . t ( "Te budynki pozostają na planecie i zajmują pola, ale nie zapewniają efektów ani nie można ich rozbudować. Odzyskają działanie, gdy kolonię przejmie cywilizacja ich rasy. Możesz budować własne budynki rasowe na wolnych polach." ) , 22 , "a0b3a4" ) )
        layout [ "footer" ] . add_child ( _label ( I18n . t ( "Nieaktywne budynki innych ras" ) , 22 , "edc77a" ) )
    building_carousel . refresh ( )


func _make_resource_hud ( shell : VBoxContainer ) -> void :
    var resources_row : HBoxContainer = _row ( shell )
    for key : String in RESOURCE_KEYS :
        var body : VBoxContainer = _card ( resources_row )
        body . add_theme_constant_override ( "separation" , 3 )
        var panel : PanelContainer = body . get_parent ( ) as PanelContainer
        panel . add_theme_stylebox_override ( "panel" , _style ( "101010" , "262626" , 16 , 10 ) )
        var amount_row : HBoxContainer = _row ( body )
        amount_row . add_theme_constant_override ( "separation" , 5 )
        amount_row . add_child ( _icon ( key , 30 ) )
        var count : Label = _token_label ( "—" , 27 , "ffc56f" if key == "fuel" else "e7eee4" )
        amount_row . add_child ( count )
        body . add_child ( _label ( I18n . t ( str ( RESOURCE_NAMES [ key ] ) ) . capitalize ( ) , 22 , "a0b3a4" ) )
        var rate : Label = _token_label ( I18n . t ( "— / h" ) , 22 , "93aa9a" )
        body . add_child ( rate )
        var capacity : Label = _token_label ( "" , 19 , "a0b3a4" )
        capacity . name = "StorageCapacity_" + key
        capacity . visible = false
        body . add_child ( capacity )
        resource_labels [ key ] = { "count" : count , "rate" : rate , "capacity" : capacity }
    storage_warning = _label ( "" , 20 , "ff9287" )
    storage_warning . name = "StorageFullWarning"
    storage_warning . visible = false
    shell . add_child ( storage_warning )


func _refresh_resource_hud ( ) -> void :
    var any_full : bool = false
    for key : String in RESOURCE_KEYS :
        var controls : Dictionary = resource_labels [ key ]
        var count : Label = controls [ "count" ]
        var rate : Label = controls [ "rate" ]
        var amount : float = float ( state . get ( "resources" , { } ) . get ( key , 0 ) )
        var capacity : float = ResourceInfo . storage_capacity ( state , key )
        var full : bool = ResourceInfo . storage_full ( state , key )
        any_full = any_full or full
        count . text = _number ( amount )
        count . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ff9287" if full else "ffc56f" if key == "fuel" else "e7eee4" ) ) )
        rate . text = I18n . t ( "+%s / h" ) % _number ( 0.0 if full else PlayerActivityScript . production_rate ( state , key ) )
        var capacity_label : Label = controls . get ( "capacity" )
        if capacity_label != null :
            capacity_label . visible = capacity > 0
            capacity_label . text = I18n . t ( "Limit: %s" ) % _number ( capacity ) if capacity > 0 else ""
            capacity_label . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ff9287" if full else "a0b3a4" ) ) )
            capacity_label . tooltip_text = I18n . t ( "Pojemność magazynu: %s" ) % _stat_number ( capacity )
        count . tooltip_text = I18n . t ( str ( RESOURCE_NAMES [ key ] ) ) . capitalize ( ) + ": " + _stat_number ( amount )
        if capacity > 0 :
            count . tooltip_text += " / " + _stat_number ( capacity )
        count . accessibility_name = count . tooltip_text
    if storage_warning != null :
        storage_warning . text = I18n . t ( "Magazyn pełny — rozbuduj skarbiec" )
        storage_warning . visible = any_full


func _refresh_owned_planets ( ) -> void :
    var planets : Array = state . get ( "own_planets" , [ ] )
    var signature : String = JSON . stringify ( planets )
    if signature != own_signature :
        own_signature = signature
        planet_picker . clear ( )
        for planet : Dictionary in planets :
            planet_picker . add_item ( str ( planet . get ( "name" , "" ) ) )
            planet_picker . set_item_metadata ( planet_picker . item_count - 1 , str ( planet . get ( "id" , "" ) ) )
    for index : int in range ( planet_picker . item_count ) :
        if str ( planet_picker . get_item_metadata ( index ) ) == selected_planet :
            planet_picker . select ( index )


func _select_owned_planet ( index : int ) -> void :
    if refreshing :
        return
    if request_pending :
        _refresh_owned_planets ( )
        _notify ( I18n . t ( "Poczekaj na odpowiedź serwera i wybierz planetę ponownie." ) , true )
        return
    requested_planet = str ( planet_picker . get_item_metadata ( index ) )
    _invalidate_quote ( )
    _poll ( true )


func _refresh_catalog ( entries : Array , list : BoxContainer , rows : Dictionary , kind : String ) -> void :


    var present : Dictionary = { }
    var unique_count : int = 0
    for entry : Dictionary in entries :
        present [ str ( entry . get ( "key" , "" ) ) ] = true
        if kind in [ "build" , "research" ] and bool ( entry . get ( "unique" , false ) ) :
            unique_count += 1
    for old_key : String in rows . keys ( ) :
        if not present . has ( old_key ) :
            var obsolete : Control = rows [ old_key ] [ "panel" ]
            obsolete . get_parent ( ) . remove_child ( obsolete )
            obsolete . queue_free ( )
            rows . erase ( old_key )
    var accent : String = _race_building_accent ( )
    if kind == "build" :


        unique_building_section . visible = false
        unique_building_heading . text = I18n . t ( "Budynki rasy · " ) + _server_text ( _selected_race ( ) . get ( "name" , I18n . t ( "Twoje imperium" ) ) )
        unique_building_heading . add_theme_color_override ( "font_color" , _ui_color ( Color ( accent ) ) )
        building_heading . text = I18n . t ( "Rozbudowa kolonii" )
        building_heading . hide ( )
    elif kind == "research" :
        unique_research_section . visible = unique_count > 0
        unique_research_heading . text = I18n . t ( "Badania rasy · " ) + _server_text ( _selected_race ( ) . get ( "name" , I18n . t ( "Twoje imperium" ) ) )
        unique_research_heading . add_theme_color_override ( "font_color" , _ui_color ( Color ( accent ) ) )
    var layout_changed: bool = false
    var common_index : int = 0
    var unique_index : int = 0
    for entry : Dictionary in entries :
        var key : String = str ( entry . get ( "key" , "" ) )
        var is_unique : bool = kind in [ "build" , "research" ] and bool ( entry . get ( "unique" , false ) )
        var target_list : BoxContainer = list
        if is_unique and kind == "research" :
            target_list = unique_research_list
        if not rows . has ( key ) :
            var card : VBoxContainer = _card ( target_list )
            card . add_theme_constant_override ( "separation" , 10 )
            var created_badge : Label = _label ( "" , 22 )
            created_badge . visible = false
            card . add_child ( created_badge )
            var picture : Control = _art_panel ( card , _entry_art_key ( entry , key ) , 88 )
            var overlay : VBoxContainer = _art_caption ( picture )
            var created_heading : Label = _label ( "" , 27 )
            overlay . add_child ( created_heading )
            var created_level : Label = _label ( "" , 22 , "91c89b" )
            overlay . add_child ( created_level )
            var role : Label = _label ( "" , 22 , "a5d5ac" )
            role . visible = false
            card . add_child ( role )
            var effects : VBoxContainer = VBoxContainer . new ( )
            effects . visible = false
            card . add_child ( effects )
            var current_effect : Label = _label ( "" , 22 , "c9d9cb" )
            var next_effect : Label = _label ( "" , 22 )
            effects . add_child ( current_effect )
            effects . add_child ( next_effect )
            var requirements : VBoxContainer = VBoxContainer . new ( )
            requirements . visible = false
            card . add_child ( requirements )
            var header : HBoxContainer = _row ( card )
            var price_box : VBoxContainer = VBoxContainer . new ( )
            price_box . size_flags_horizontal = Control . SIZE_EXPAND_FILL
            header . add_child ( price_box )
            var costs : Dictionary = _cost_icons ( price_box )
            var created_description : Label = _label ( "" , 22 , "a0b3a4" )
            created_description . visible = false
            var details : Button = _button ( "i" , func ( ) -> void : created_description . visible = not created_description . visible )
            details . tooltip_text = I18n . t ( "Opis i wymagania" )
            details . custom_minimum_size = Vector2 ( 62 , 62 )
            details . size_flags_horizontal = Control . SIZE_SHRINK_END
            details . size_flags_vertical = Control . SIZE_SHRINK_CENTER
            header . add_child ( details )
            card . add_child ( created_description )
            var stats_flow : HFlowContainer = HFlowContainer . new ( )
            stats_flow . add_theme_constant_override ( "h_separation" , 18 )
            stats_flow . visible = kind in [ "ship" , "defense" ]
            card . add_child ( stats_flow )
            var attack_stat : Label = _token_label ( "" , 22 , "e6b774" )
            var hull_stat : Label = _token_label ( "" , 22 , "c9d9cb" )
            var capacity_stat : Label = _token_label ( "" , 22 , "a0b3a4" )
            stats_flow . add_child ( attack_stat )
            stats_flow . add_child ( hull_stat )
            stats_flow . add_child ( capacity_stat )
            var batch_effect : Label = _label ( "" , 22 , "f39b90" )
            batch_effect . visible = false
            card . add_child ( batch_effect )
            var production_effect : Label = _label ( "" , 22 , "99d886" )
            production_effect . visible = false
            card . add_child ( production_effect )
            var refund : VBoxContainer = VBoxContainer . new ( )
            refund . visible = false
            card . add_child ( refund )
            refund . add_child ( _label ( I18n . t ( "Recykling · zwrot po ukończeniu" ) , 22 , "f18c85" ) )
            var refund_costs : Dictionary = _cost_icons ( refund )
            var progress_panel : VBoxContainer = VBoxContainer . new ( )
            progress_panel . visible = false
            card . add_child ( progress_panel )
            var progress_label : Label = _label ( "" , 22 , "d4ebd6" )
            progress_panel . add_child ( progress_label )
            var progress_bar : ProgressBar = _meter ( "91c89b" )
            progress_bar . custom_minimum_size . y = 22
            progress_panel . add_child ( progress_bar )
            var amount : MobileQuantityScript = null
            if kind in [ "ship" , "defense" ] :
                card . add_child ( _label ( I18n . t ( "Zamawiane jednostki" ) if kind == "defense" else I18n . t ( "Zamawiane statki" ) , 22 , "a0b3a4" ) )
                amount = _spin ( 1 , 20 )
                amount . value_changed . connect ( func ( _value : float ) -> void : _refresh_catalog_price ( rows , key ) )
                card . add_child ( amount )
            var action_row : HBoxContainer = _row ( card )
            var duration : HBoxContainer = _row ( action_row )
            duration . add_child ( _icon ( "time" , 26 ) )
            var created_time : Label = _token_label ( "" , 22 , "a0b3a4" )
            duration . add_child ( created_time )
            var created_action : Button = _button ( I18n . t ( "Buduj" ) if kind != "research" else I18n . t ( "Badaj" ) , _catalog_action . bind ( kind , key ) , true )
            created_action . custom_minimum_size = Vector2 ( 176 , 72 )
            created_action . size_flags_horizontal = Control . SIZE_SHRINK_END
            action_row . add_child ( created_action )
            var created_reason : Label = _label ( "" , 22 , "e6b774" )
            card . add_child ( created_reason )
            rows [ key ] = { "panel" : card . get_parent ( ) , "badge" : created_badge , "effects" : effects , "effect_current" : current_effect , "effect_next" : next_effect , "requirements" : requirements , "requirements_signature" : "" , "batch_effect" : batch_effect , "production_effect" : production_effect , "refund" : refund , "refund_costs" : refund_costs , "art" : picture . get_node ( "Illustration" ) , "stats" : stats_flow , "attack_stat" : attack_stat , "hull_stat" : hull_stat , "capacity_stat" : capacity_stat , "heading" : created_heading , "level" : created_level , "role" : role , "description" : created_description , "costs" : costs , "time" : created_time , "reason" : created_reason , "action" : created_action , "amount" : amount , "progress_panel" : progress_panel , "progress_label" : progress_label , "progress_bar" : progress_bar , "kind" : kind }
        var controls : Dictionary = rows [ key ]
        var panel : PanelContainer = controls [ "panel" ]
        if panel . get_parent ( ) != target_list :
            panel . reparent ( target_list )
        var desired_index: int = common_index + unique_index if kind == "build" else unique_index if is_unique else common_index
        if panel.get_index() != desired_index:
            target_list.move_child(panel, desired_index)
            layout_changed = true
        if is_unique :
            unique_index += 1
        else :
            common_index += 1

        var definition: Array = [entry, I18n.locale, accent, is_unique]
        if controls.get("definition_cache", []) == definition:
            controls["entry"] = entry
            _refresh_catalog_price(rows, key)
            continue
        controls["definition_cache"] = definition.duplicate(true)
        layout_changed = true
        if bool ( controls . get ( "unique" , false ) ) != is_unique or str ( controls . get ( "accent" , "" ) ) != accent :
            panel . add_theme_stylebox_override ( "panel" , _style ( "101010" , accent if is_unique else "262626" , 16 , 12 ) )
            controls [ "unique" ] = is_unique
            controls [ "accent" ] = accent
        controls [ "badge" ] . visible = is_unique and kind in [ "build" , "research" ]
        controls [ "badge" ] . text = I18n . t ( "BADANIE RASY" ) if kind == "research" and is_unique else I18n . t ( "Budynki rasy" ) if kind == "build" and is_unique else ""
        controls [ "badge" ] . add_theme_color_override ( "font_color" , _ui_color ( Color ( accent ) ) )
        var heading : Label = controls [ "heading" ]
        var level : Label = controls [ "level" ]
        var description : Label = controls [ "description" ]
        var action : Button = controls [ "action" ]
        var illustration : TextureRect = controls [ "art" ]
        var art_key : String = _entry_art_key ( entry , key )
        if illustration . texture == null or str ( controls . get ( "art_key" , "" ) ) != art_key :
            illustration . texture = ArtLibrary . texture ( art_key )
            controls [ "art_key" ] = art_key
        heading . text = _server_text ( entry . get ( "name" , I18n . t ( str ( NAMES . get ( key , key ) ) ) ) )
        var current_level : int = int ( entry . get ( "count" , 0 ) if kind in [ "ship" , "defense" ] else entry . get ( "level" , 0 ) )
        level . text = I18n . t ( "W bazie: %d" ) % current_level if kind in [ "ship" , "defense" ] else I18n . t ( "Poziom %d" ) % current_level
        if not kind in [ "build" , "defense" ] and int ( entry . get ( "max_level" , 0 ) ) > 0 :
            level . text += " / %d" % int ( entry [ "max_level" ] )
        level . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ffffff" if kind in [ "ship" , "defense" ] else accent if is_unique else "91c89b" ) ) )
        _refresh_catalog_details ( controls , entry , accent )
        description . text = _server_text ( entry . get ( "description" , "" ) )
        var role_label : Label = controls [ "role" ]
        var role_key : String = str ( entry . get ( "role" , key ) )
        role_label . text = _server_text ( entry . get ( "role_name" , { "interceptor" : I18n . t ( "Szybka eskorta" ) , "siege" : I18n . t ( "Ciężki okręt ofensywny" ) , "freighter" : I18n . t ( "Transport dużych ładunków" ) } . get ( role_key , "" ) ) )
        if kind in [ "ship" , "defense" ] and float ( entry . get ( "swarm_attack_multiplier" , 1.0 ) ) > 1.0 :
            role_label . text = I18n . t ( "Przeciw Rojowi · +%s%% ataku" ) % _stat_number ( ( float ( entry [ "swarm_attack_multiplier" ] ) - 1.0 ) * 100.0 )
        if kind in [ "ship" , "research" , "defense" ] :

            role_label . text = CatalogDetailsScript . brief_description ( self , entry )
        role_label . visible = kind in [ "ship" , "research" , "defense" ] and not role_label . text . is_empty ( )
        if kind in [ "ship" , "defense" ] :
            if entry . has ( "speed" ) :
                description . text += I18n . t ( "\nPrędkość: %s · Zużycie paliwa: %s" ) % [ _stat_number ( float ( entry . get ( "effective_speed" , entry . get ( "speed" , 0 ) ) ) ) , _stat_number ( float ( entry . get ( "effective_fuel" , entry . get ( "fuel" , 0 ) ) ) ) ]
            if float ( entry . get ( "regeneration_fraction" , 0 ) ) > 0 :
                description . text += I18n . t ( "\nRegeneracja: %s%%" ) % _stat_number ( float ( entry . get ( "regeneration_fraction" , 0 ) ) * 100 )
            if float ( entry . get ( "defense_regeneration_bonus" , 0 ) ) > 0 :
                description . text += I18n . t ( "\nRegeneracja w obronie tej planety: %s%%" ) % _stat_number ( float ( entry . get ( "defense_regeneration_fraction" , 0 ) ) * 100 )
            controls [ "attack_stat" ] . text = I18n . t ( "Atak %s" ) % _stat_number ( float ( entry . get ( "effective_attack" , entry . get ( "attack" , 0 ) ) ) )
            controls [ "hull_stat" ] . text = I18n . t ( "Kadłub %s" ) % _stat_number ( float ( entry . get ( "hull" , 0 ) ) )
            controls [ "capacity_stat" ] . visible = kind == "ship"
            controls [ "capacity_stat" ] . text = I18n . t ( "Ładownia %s" ) % _stat_number ( float ( entry . get ( "capacity" , 0 ) ) )
        action . text = I18n . t ( "Badaj" ) if kind == "research" else I18n . t ( "Buduj" ) if kind in [ "ship" , "defense" ] or current_level == 0 else I18n . t ( "Ulepsz" )
        if not kind in [ "ship" , "defense" ] and int ( entry . get ( "max_level" , 0 ) ) > 0 and current_level >= int ( entry [ "max_level" ] ) :
            action . text = I18n . t ( "Maksimum" )
        controls [ "entry" ] = entry
        _refresh_catalog_price ( rows , key )
    if not layout_changed:
        return
    if kind == "build" and building_carousel != null :
        if megastructure_ui != null and megastructure_ui . has_method ( "refresh_building_cards" ) :
            megastructure_ui . refresh_building_cards ( list )
        building_carousel . refresh ( )
    elif kind == "ship" and ship_carousel != null :
        ship_carousel . refresh ( )
    elif kind == "defense" and list . get_parent ( ) . get_parent ( ) . has_method ( "refresh" ) :
        list . get_parent ( ) . get_parent ( ) . refresh ( )


func _race_building_accent ( ) -> String :

    return "72b8f4"


func _refresh_catalog_details ( controls : Dictionary , entry : Dictionary , accent : String ) -> void :
    var current_text : String = _server_text ( entry . get ( "effect_current" , "" ) )
    var next_text : String = _server_text ( entry . get ( "effect_next" , "" ) )
    if int ( entry . get ( "max_level" , 0 ) ) > 0 and int ( entry . get ( "level" , 0 ) ) >= int ( entry [ "max_level" ] ) :
        next_text = ""
    var current : Label = controls [ "effect_current" ]
    var next : Label = controls [ "effect_next" ]
    current . visible = not current_text . is_empty ( )
    next . visible = not next_text . is_empty ( )
    var initial_caption : String = I18n . t ( "Jeszcze nie zbadano" ) if str ( controls [ "kind" ] ) == "research" else I18n . t ( "Jeszcze nie zbudowano" )
    current . text = I18n . t ( "Teraz: " ) + current_text if int ( entry . get ( "level" , 0 ) ) > 0 else initial_caption
    next . text = I18n . t ( "Następny: " ) + next_text
    next . add_theme_color_override ( "font_color" , _ui_color ( Color ( accent ) ) )
    controls [ "effects" ] . visible = current . visible or next . visible
    var requirements : VBoxContainer = controls [ "requirements" ]
    var supplied : Array = entry . get ( "requirements" , [ ] )
    var signature : String = JSON . stringify ( supplied )
    if signature != str ( controls [ "requirements_signature" ] ) :
        controls [ "requirements_signature" ] = signature
        for child : Node in requirements . get_children ( ) :
            requirements . remove_child ( child )
            child . queue_free ( )
        for requirement : Dictionary in supplied :
            var met : bool = bool ( requirement . get ( "met" , false ) )
            var group : String = str ( requirement . get ( "group" , "buildings" ) )
            var requirement_name : String = _server_text ( requirement . get ( "name" , _catalog_name ( str ( requirement . get ( "key" , "" ) ) , group ) ) )
            var caption : String = I18n . t ( "%s %s · poz. %d" ) % [ "✓" if met else I18n . t ( "Wymaga:" ) , requirement_name , int ( requirement . get ( "level" , 0 ) ) ]
            requirements . add_child ( _label ( caption , 22 , "a0b3a4" if met else "e6b774" ) )
    requirements . visible = not supplied . is_empty ( )


func _batch_time_reduction ( entry : Dictionary , amount : int ) -> float :
    var per_extra : float = maxf ( 0.0 , float ( entry . get ( "batch_time_reduction_per_extra" , 0 ) ) )
    var cap : float = clampf ( float ( entry . get ( "batch_time_reduction_cap" , 0 ) ) , 0.0 , 1.0 )
    return minf ( cap , per_extra * maxi ( 0 , amount - 1 ) )


func _catalog_seconds ( entry : Dictionary , amount : int = 1 ) -> float :
    var seconds : float = float ( entry . get ( "seconds" , 0 ) ) * amount
    if entry . has ( "batch_time_reduction_per_extra" ) :
        return maxf ( 1.0 , ceilf ( seconds * ( 1.0 - _batch_time_reduction ( entry , amount ) ) ) )
    return seconds


func _refresh_catalog_price ( rows : Dictionary , key : String ) -> void :
    if not rows . has ( key ) or not rows [ key ] . has ( "entry" ) :
        return
    var controls : Dictionary = rows [ key ]
    var entry : Dictionary = controls [ "entry" ]
    var amount_control : MobileQuantityScript = controls [ "amount" ] as MobileQuantityScript
    var amount : int = int ( amount_control . value ) if amount_control != null else 1
    var affordability: Array = []
    for resource: String in RESOURCE_KEYS:
        affordability.append(float(entry.get("cost", {}).get(resource, 0)) * amount <= float(state.get("resources", {}).get(resource, 0)))
    var price_context: Array = [entry, amount, affordability, I18n.locale, selected_planet,
        request_pending, update_required, not uncertain_action.is_empty(), requested_planet,
        state.get("queue", []), state.get("queues", {}), state.get("planned_orders", []),
        state.get("premium", {}), state.get("limits", {}),
        planned_queue_ui.busy() if planned_queue_ui != null else false]
    if controls.get("price_cache", []) == price_context:
        return
    controls["price_cache"] = price_context.duplicate(true)
    var enough : bool = true
    for resource : String in RESOURCE_KEYS :
        var cost : float = float ( entry . get ( "cost" , { } ) . get ( resource , 0 ) ) * amount
        var owned : float = float ( state . get ( "resources" , { } ) . get ( resource , 0 ) )
        var item : Dictionary = controls [ "costs" ] [ resource ]
        var cost_row : HBoxContainer = item [ "row" ]
        cost_row . visible = cost > 0
        var caption : Label = item [ "amount" ]
        caption . text = _number ( cost )
        caption . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ff9287" ) ) if cost > owned else _ui_color ( Color ( "c9d9cb" ) ) )
        if cost > owned :
            enough = false
    var duration : Label = controls [ "time" ]
    duration . text = _duration ( _catalog_seconds ( entry , amount ) )
    var batch_effect : Label = controls [ "batch_effect" ]
    var batch_reduction : float = _batch_time_reduction ( entry , amount ) if str ( controls [ "kind" ] ) == "ship" else 0.0
    batch_effect . visible = batch_reduction > 0.0
    batch_effect . text = I18n . t ( "Produkcja seryjna · −%s%% czasu" ) % _stat_number ( batch_reduction * 100.0 )
    batch_effect . add_theme_color_override ( "font_color" , _ui_color ( Color ( "f39b90" ) ) )
    if str ( controls [ "kind" ] ) == "research" and int ( entry . get ( "crystal_refund" , 0 ) ) > 0 :
        batch_effect . visible = true
        batch_effect . text = I18n . t ( "Po ukończeniu: zwrot %s zwykłych kryształów" ) % _number ( float ( entry [ "crystal_refund" ] ) )
        batch_effect . add_theme_color_override ( "font_color" , _ui_color ( Color ( "72b8f4" ) ) )
    var production : Label = controls [ "production_effect" ]
    var multiplier : float = maxf ( 1.0 , float ( entry . get ( "production_multiplier" , 1.0 ) ) )
    production . visible = str ( controls [ "kind" ] ) == "ship" and multiplier > 1.0
    production . text = I18n . t ( "Namnażanie ×" ) + _stat_number ( multiplier )
    var refund_rate : float = clampf ( float ( entry . get ( "construction_refund_rate" , 0 ) ) , 0.0 , 1.0 )
    controls [ "refund" ] . visible = str ( controls [ "kind" ] ) in [ "build" , "ship" , "defense" ] and refund_rate > 0.0
    for resource : String in RESOURCE_KEYS :


        var refunded : int = floori ( roundf ( float ( entry . get ( "cost" , { } ) . get ( resource , 0 ) ) * amount * refund_rate * 1000000.0 ) / 1000000.0 )
        var refund_item : Dictionary = controls [ "refund_costs" ] [ resource ]
        refund_item [ "row" ] . visible = refunded > 0
        refund_item [ "amount" ] . text = "+" + _number ( refunded )
    var reason : Label = controls [ "reason" ]
    reason . text = _server_text ( entry . get ( "reason" , "" ) )

    if reason . text . is_empty ( ) and not enough :
        reason . text = I18n . t ( "Brakuje surowców." )
    reason . visible = not reason . text . is_empty ( )
    var action : Button = controls [ "action" ]
    action . disabled = not bool ( entry . get ( "enabled" , false ) ) or not enough or update_required
    if compact_ui != null :
        compact_ui . compact_catalog ( controls )
    if planned_queue_ui != null :
        planned_queue_ui . refresh_action_button ( action , entry , str ( controls [ "kind" ] ) , amount )


func _ask_cancel_project ( queue_id : String = "" ) -> void :
    if request_pending or not uncertain_action . is_empty ( ) or update_required :
        return
    var task : Dictionary = project_ui . find_task ( queue_id ) if not queue_id . is_empty ( ) else project_ui . task_for ( "build" )
    if task . is_empty ( ) or float ( task . get ( "ends_at" , 0 ) ) <= _server_now ( ) :
        return
    cancel_project_payload = { "type" : "cancel_project" , "planet_id" : str ( task . get ( "planet_id" , selected_planet ) ) , "queue_id" : str ( task . get ( "id" , "" ) ) , "request_id" : _new_request_id ( ) }
    if not is_instance_valid ( cancel_project_dialog ) :
        cancel_project_dialog = ConfirmationDialog . new ( )
        cancel_project_dialog . name = "CancelProjectConfirmation"
        cancel_project_dialog . dialog_autowrap = true
        cancel_project_dialog . confirmed . connect ( _confirm_cancel_project )
        add_child ( cancel_project_dialog )
    cancel_project_dialog . title = I18n . t ( "Anulować projekt?" )
    cancel_project_dialog . get_ok_button ( ) . text = I18n . t ( "Anuluj projekt" )
    cancel_project_dialog . get_cancel_button ( ) . text = I18n . t ( "Wróć" )
    var refund : String = I18n . t ( "Brak zapisanego kosztu tego starszego projektu. Anulowanie bez zwrotu." )
    if task . has ( "paid_cost" ) and task [ "paid_cost" ] is Dictionary :
        refund = I18n . t ( "Zwrot surowców: %s" ) % _cost ( task [ "paid_cost" ] )
    cancel_project_dialog . dialog_text = project_ui . task_name ( task ) + "\n\n" + refund + "\n" + I18n . t ( "Anulowana zostanie cała partia. Żadna jednostka nie powstanie. Zwrot ogranicza pojemność magazynu." )
    cancel_project_dialog . popup_centered_clamped ( Vector2i ( 600 , 300 ) , 0.9 )


func _confirm_cancel_project ( ) -> void :
    var payload : Dictionary = cancel_project_payload . duplicate ( true )
    cancel_project_payload . clear ( )
    if payload . is_empty ( ) or request_pending or not uncertain_action . is_empty ( ) or update_required :
        return
    var task : Dictionary = project_ui . find_task ( str ( payload . get ( "queue_id" , "" ) ) )
    if task . is_empty ( ) or str ( task . get ( "planet_id" , selected_planet ) ) != str ( payload . get ( "planet_id" , "" ) ) :
        _notify ( I18n . t ( "Projekt już się zmienił. Odśwież widok." ) , true )
        return
    _request ( "/api/action" , payload , "action" )


func _catalog_action ( kind : String , key : String ) -> void :
    if request_pending or not uncertain_action . is_empty ( ) or update_required or not requested_planet . is_empty ( ) :
        return
    if planned_queue_ui != null and planned_queue_ui . lane_busy ( kind ) :
        planned_queue_ui . add ( kind , key )
        return
    var group : String = str ( { "build" : "buildings" , "research" : "research" , "ship" : "ships" , "defense" : "defenses" } . get ( kind , "" ) )
    var entry : Dictionary = _catalog_entry ( key , group )
    if entry . is_empty ( ) or not bool ( entry . get ( "enabled" , false ) ) :
        return
    var action : Dictionary = { "type" : kind , "planet_id" : selected_planet , "key" : key , "request_id" : _new_request_id ( ) }
    if kind in [ "ship" , "defense" ] :
        var controls : Dictionary = defense_rows [ key ] if kind == "defense" else ship_rows [ key ]
        var amount : MobileQuantityScript = controls [ "amount" ]
        amount . apply ( )
        action [ "amount" ] = int ( amount . value )
    if planned_queue_ui != null and not planned_queue_ui . has_resources ( entry , int ( action . get ( "amount" , 1 ) ) ) :
        return
    _request ( "/api/action" , action , "action" )
    if compact_ui != null :
        compact_ui . close_details ( )


func _plan_catalog_action ( kind : String , key : String ) -> void :
    if planned_queue_ui != null :
        planned_queue_ui . add ( kind , key )


func _galaxy_catalog ( ) -> Array :
    var entries : Array = state . get ( "galaxies" , [ ] )
    if entries . is_empty ( ) :
        return [ { "id" : "g1" , "name" : "Aurora" , "art_key" : "galaxies/aurora" } ]
    return entries


func _galaxy_name ( id : String ) -> String :
    for entry : Dictionary in _galaxy_catalog ( ) :
        if str ( entry . get ( "id" , "" ) ) == id :
            return str ( entry . get ( "name" , id ) )
    return id


func _visible_systems ( ) -> Array :
    var result : Array = [ ]
    for system : Dictionary in state . get ( "galaxy" , [ ] ) :
        if str ( system . get ( "galaxy_id" , "g1" ) ) == selected_galaxy :
            result . append ( system )
    return result


func _select_galaxy ( index : int ) -> void :
    if index < 0 or index >= galaxy_picker . item_count :
        return
    selected_galaxy = str ( galaxy_picker . get_item_metadata ( index ) )
    selected_system = ""
    var visible : Array = _visible_systems ( )
    if not visible . is_empty ( ) :
        selected_system = str ( visible [ 0 ] . get ( "id" , "" ) )
    galaxy_signature = ""
    _refresh_galaxy ( )
    galaxy_map . call ( "reset_view" )
    _show_full_galaxy_map ( false )
    galaxy_toggle . text = I18n . t ( "Układ" )


func _refresh_galaxy ( ) -> void :
    var all_systems : Array = state . get ( "galaxy" , [ ] )

    if selected_system . is_empty ( ) :
        for system : Dictionary in all_systems :
            for planet : Dictionary in system . get ( "planets" , [ ] ) :
                if str ( planet . get ( "id" , "" ) ) == selected_planet :
                    selected_system = str ( system . get ( "id" , "" ) )
    for system : Dictionary in all_systems :
        if str ( system . get ( "id" , "" ) ) == selected_system :
            selected_galaxy = str ( system . get ( "galaxy_id" , "g1" ) )
    var catalog : Array = _galaxy_catalog ( )
    var known_galaxy : bool = false
    for entry : Dictionary in catalog :
        if str ( entry . get ( "id" , "" ) ) == selected_galaxy :
            known_galaxy = true
    if not known_galaxy :
        selected_galaxy = str ( catalog [ 0 ] . get ( "id" , "g1" ) )
        selected_system = ""
    var choices_signature : String = JSON . stringify ( catalog )
    if choices_signature != galaxy_choices_signature :
        galaxy_choices_signature = choices_signature
        galaxy_picker . clear ( )
        for entry : Dictionary in catalog :
            var title : String = str ( entry . get ( "name" , "" ) )
            var own_count : int = int ( entry . get ( "own_colonies" , 0 ) )
            if own_count > 0 :
                title += " · " + I18n . t ( "Twoje kolonie: %d" ) % own_count
            galaxy_picker . add_item ( title )
            galaxy_picker . set_item_metadata ( galaxy_picker . item_count - 1 , str ( entry . get ( "id" , "" ) ) )
    var active_galaxy : Dictionary = { }
    for index : int in range ( galaxy_picker . item_count ) :
        if str ( galaxy_picker . get_item_metadata ( index ) ) == selected_galaxy :
            galaxy_picker . select ( index )
    for entry : Dictionary in catalog :
        if str ( entry . get ( "id" , "" ) ) == selected_galaxy :
            active_galaxy = entry
    previous_galaxy_button . disabled = galaxy_picker . item_count < 2
    next_galaxy_button . disabled = galaxy_picker . item_count < 2
    galaxy_summary . text = str ( active_galaxy . get ( "description" , "" ) )
    if active_galaxy . has ( "systems_count" ) :
        galaxy_summary . text += "\n" + I18n . t ( "Układy: %d · Znane planety: %d · Znane ule: %d" ) % [ int ( active_galaxy . get ( "systems_count" , 0 ) ) , int ( active_galaxy . get ( "planets_count" , 0 ) ) , int ( active_galaxy . get ( "hives_count" , 0 ) ) ]
    galaxy_travel_note . text = I18n . t ( "Przeglądanie galaktyk jest bezpłatne. Koszt lotu sprawdzisz po wybraniu floty i celu." )
    var minimum_fuel : int = int ( active_galaxy . get ( "minimum_jump_fuel" , 0 ) )
    if minimum_fuel > 0 :
        galaxy_travel_note . text += "\n" + I18n . t ( "Skok z %s: co najmniej %s paliwa + koszt floty." ) % [ _galaxy_name ( str ( state . get ( "planet_galaxy_id" , "g1" ) ) ) , _exact_integer ( minimum_fuel ) ]
    galaxy_map . call ( "set_galaxy_art" , ArtLibrary . texture ( str ( active_galaxy . get ( "art_key" , "galaxies/aurora" ) ) ) )
    var galaxy : Array = _visible_systems ( )
    var signature : String = selected_galaxy + JSON . stringify ( all_systems )
    var owner : String = str ( state . get ( "player" , { } ) . get ( "id" , "" ) )
    var selection_exists : bool = false
    for system : Dictionary in galaxy :
        if str ( system . get ( "id" , "" ) ) == selected_system :
            selection_exists = true
    if not selection_exists and not galaxy . is_empty ( ) :
        selected_system = str ( galaxy [ 0 ] . get ( "id" , "" ) )
    if signature != galaxy_signature :
        galaxy_signature = signature
        system_picker . clear ( )
        target_picker . clear ( )
        target_picker . add_item ( I18n . t ( "Wybierz cel misji" ) )
        target_picker . set_item_metadata ( 0 , "" )
        for system : Dictionary in galaxy :
            system_picker . add_item ( str ( system . get ( "name" , "" ) ) )
            system_picker . set_item_metadata ( system_picker . item_count - 1 , str ( system . get ( "id" , "" ) ) )
        for system : Dictionary in all_systems :
            if system . has ( "scout_target_id" ) :
                target_picker . add_item ( "%s / %s · %s" % [ _galaxy_name ( str ( system . get ( "galaxy_id" , "g1" ) ) ) , str ( system . get ( "name" , "" ) ) , I18n . t ( "Zbadaj układ" ) ] )
                target_picker . set_item_metadata ( target_picker . item_count - 1 , str ( system [ "scout_target_id" ] ) )
            for planet : Dictionary in system . get ( "planets" , [ ] ) :
                target_picker . add_item ( "%s / %s" % [ _galaxy_name ( str ( system . get ( "galaxy_id" , "g1" ) ) ) , str ( planet . get ( "name" , "" ) ) ] )
                target_picker . set_item_metadata ( target_picker . item_count - 1 , str ( planet . get ( "id" , "" ) ) )
        _sync_target ( )
    galaxy_map . call ( "set_data" , galaxy , owner , selected_system )
    galaxy_map.call("set_fleets", state.get("fleets", []), _server_now())
    for index : int in range ( system_picker . item_count ) :
        if str ( system_picker . get_item_metadata ( index ) ) == selected_system :
            system_picker . select ( index )
    _refresh_system_planets ( )


func _choose_system ( id : String ) -> void :
    selected_system = id
    _refresh_galaxy ( )


func _refresh_system_planets ( ) -> void :
    if compact_ui != null :
        compact_ui . refresh_planets ( )
        return
    var active : Dictionary = { }
    for system : Dictionary in state . get ( "galaxy" , [ ] ) :
        if str ( system . get ( "id" , "" ) ) == selected_system :
            active = system
    var signature : String = JSON . stringify ( active ) + str ( state . get ( "player" , { } ) . get ( "id" , "" ) ) + selected_planet
    if signature == system_signature :
        return
    system_signature = signature
    _clear ( planet_list )
    planet_actions . clear ( )
    system_heading . text = str ( active . get ( "name" , I18n . t ( "Wybierz układ" ) ) )
    system_coordinates . text = I18n . t ( "Sektor %s:%s · %d planet" ) % [ _stat_number ( float ( active . get ( "x" , 0 ) ) ) , _stat_number ( float ( active . get ( "y" , 0 ) ) ) , active . get ( "planets" , [ ] ) . size ( ) ]
    for planet : Dictionary in active . get ( "planets" , [ ] ) :
        var card : VBoxContainer = _card ( planet_list )
        var row : HBoxContainer = _row ( card )
        var art : Control = PlanetArtScript . new ( )
        art . custom_minimum_size = Vector2 ( 144 , 144 )
        art . set ( "planet_id" , str ( planet . get ( "id" , "" ) ) )
        art . set ( "alien_world" , str ( planet . get ( "owner_type" , "empty" ) ) == "alien" )
        row . add_child ( art )
        var info : VBoxContainer = VBoxContainer . new ( )
        info . size_flags_horizontal = Control . SIZE_EXPAND_FILL
        info . alignment = BoxContainer . ALIGNMENT_CENTER
        row . add_child ( info )
        info . add_child ( _label ( I18n . t ( "POZYCJA %s" ) % str ( int ( planet . get ( "slot" , 0 ) ) ) , 22 , "a0b3a4" ) )
        info . add_child ( _label ( str ( planet . get ( "name" , I18n . t ( "Planeta" ) ) ) + ( " · " + I18n . t ( "Chroniona" ) if float ( planet . get ( "protected_until" , 0 ) ) > _server_now ( ) else "" ) , 27 ) )
        var owner_type : String = str ( planet . get ( "owner_type" , "empty" ) )
        var owner_name : String = str ( planet . get ( "owner_name" , "" ) )
        var player_id : String = str ( state . get ( "player" , { } ) . get ( "id" , "" ) )
        var is_owned : bool = str ( planet . get ( "owner_id" , "" ) ) == player_id
        var caption : String = I18n . t ( "○ Wolna planeta" )
        if owner_type == "alien" :
            caption = "◆ " + owner_name
        elif owner_type == "player" :
            caption = I18n . t ( "● Twoja kolonia" ) if is_owned else "● " + owner_name
        info . add_child ( _label ( caption , 22 , "ff9287" if owner_type == "alien" else "91c89b" if is_owned else "ffc56f" if owner_type == "player" else "a0b3a4" ) )
        if owner_type == "player" and not str ( planet . get ( "race_name" , "" ) ) . is_empty ( ) :
            info . add_child ( _label ( str ( planet [ "race_name" ] ) , 22 , "c9d9cb" ) )
        if owner_type == "alien" :
            _swarm_planet_details ( card , planet )
        var id : String = str ( planet . get ( "id" , "" ) )
        if id == selected_planet :
            info . add_child ( _label ( I18n . t ( "Baza twojej floty" ) , 22 , "a5d5ac" ) )
        else :
            var actions : HBoxContainer = _row ( card )
            if owner_type == "empty" :
                actions . add_child ( _button ( I18n . t ( "Kolonizuj" ) , _prepare_planet_mission . bind ( id , 1 ) , true ) )
            elif is_owned :
                actions . add_child ( _button ( I18n . t ( "Transport" ) , _prepare_planet_mission . bind ( id , 3 ) , true ) )
            else :
                actions . add_child ( _button ( I18n . t ( "Zwiad" ) , _prepare_planet_mission . bind ( id , 0 ) , true ) )
                if FleetNavigationScript . Model . GalaxyGuidance . can_attempt_colonization ( state , planet , _server_now ( ) ) :
                    actions . add_child ( _button ( I18n . t ( "Przejęcie kolonii" ) , _prepare_planet_mission . bind ( id , 1 ) ) )
                var attack : Button = _button ( I18n . t ( "Najazd" ) , _prepare_planet_mission . bind ( id , 2 ) ) if owner_type == "alien" else _button ( I18n . t ( "Atak" ) , _prepare_planet_mission . bind ( id , 2 ) )
                actions . add_child ( attack )
                var protection : Label = _label ( I18n . t ( "Ochrona startowa · atak niedostępny" ) , 22 , "ffc56f" )
                card . add_child ( protection )
                planet_actions . append ( { "attack" : attack , "protection" : protection , "until" : float ( planet . get ( "protected_until" , 0 ) ) if owner_type == "player" else 0.0 } )
    _refresh_planet_protection ( )


func _refresh_planet_protection ( ) -> void :
    for entry : Dictionary in planet_actions :
        if not is_instance_valid ( entry [ "attack" ] ) :
            continue
        var protected : bool = float ( entry [ "until" ] ) > _server_now ( )
        entry [ "attack" ] . disabled = protected
        entry [ "protection" ] . visible = protected


func _prepare_planet_mission ( id : String , mission : int ) -> void :
    if update_required or mission < 0 or mission >= MISSION_KEYS . size ( ) :
        return

    selected_scout_system = ""
    selected_target = id
    _sync_target ( )
    mission_picker . select ( mission )
    _mission_changed ( mission )
    _open_fleet_missions ( )
    tabs [ 2 ] . scroll_vertical = 0

    if compact_ui != null :
        compact_ui . open_composer ( )


func _prepare_system_scout ( system_id : String ) -> void :
    if update_required :
        return
    for system : Dictionary in state . get ( "galaxy" , [ ] ) :
        if str ( system . get ( "id" , "" ) ) != system_id :
            continue
        var target : String = preload ( "res://client/scripts/galaxy_guidance_model.gd" ) . system_scout_target ( system , selected_planet )
        if target . is_empty ( ) :
            return
        selected_scout_system = system_id
        selected_target = target
        mission_picker . select ( 0 )
        _sync_target ( )
        _mission_changed ( 0 )
        _open_fleet_missions ( )
        tabs [ 2 ] . scroll_vertical = 0
        if compact_ui != null :
            compact_ui . close_details ( )
            compact_ui . open_composer ( )
        return


func _target_from_map ( id : String , owner_type : String , is_owned : bool ) -> void :
    selected_scout_system = ""
    selected_target = id
    _sync_target ( )
    if owner_type == "empty" :
        mission_picker . select ( 1 )
    elif is_owned :
        mission_picker . select ( 3 )
    else :
        mission_picker . select ( 0 )
    _mission_changed ( mission_picker . selected )
    _open_fleet_missions ( )
    tabs [ 2 ] . scroll_vertical = 0


func _select_target ( index : int ) -> void :
    selected_scout_system = ""
    selected_target = str ( target_picker . get_item_metadata ( index ) )
    if planetary_ui != null and planetary_ui . unknown_target ( selected_target ) :
        mission_picker . select ( 0 )
        _mission_changed ( 0 )
    _sync_target ( )
    _invalidate_quote ( )


func _sync_target ( ) -> void :
    for index : int in range ( target_picker . item_count ) :
        if str ( target_picker . get_item_metadata ( index ) ) == selected_target :
            target_picker . select ( index )
    target_label . text = I18n . t ( "Wybierz planetę na mapie lub z listy." )
    for system : Dictionary in state . get ( "galaxy" , [ ] ) :
        if str ( system . get ( "scout_target_id" , "" ) ) == selected_target and not selected_target . is_empty ( ) :
            target_label . text = str ( system . get ( "name" , "" ) ) + "\n" + I18n . t ( "Nieznany cel. Najpierw wyślij zwiad." )
        for planet : Dictionary in system . get ( "planets" , [ ] ) :
            if str ( planet . get ( "id" , "" ) ) == selected_target :
                var owner : String = str ( planet . get ( "owner_name" , "" ) )
                if owner . is_empty ( ) :
                    owner = I18n . t ( "Niezasiedlona" )
                target_label . text = "%s • %s\n%s" % [ str ( system . get ( "name" , "" ) ) , str ( planet . get ( "name" , "" ) ) , owner ]
    if not selected_scout_system . is_empty ( ) :
        for system : Dictionary in state . get ( "galaxy" , [ ] ) :
            if str ( system . get ( "id" , "" ) ) == selected_scout_system :
                target_label . text = str ( system . get ( "name" , selected_scout_system ) ) + "\n" + I18n . t ( "Zwiad całego układu" )
    _update_mission_hint ( )


func _mission_changed ( index : int ) -> void :
    if index == 4 :
        selected_target = str ( state . get ( "expeditions" , { } ) . get ( "zone" , { } ) . get ( "id" , "" ) )
    elif selected_target . begins_with ( "expedition:" ) :
        selected_target = ""
    if index != 0 :
        selected_scout_system = ""
    cargo_box . visible = index in [ 1 , 3 ]
    _update_mission_hint ( )
    _invalidate_quote ( )


func _update_mission_hint ( ) -> void :
    if mission_hint == null :
        return
    if megastructure_ui != null :
        megastructure_ui . tick ( )
    var captions : Array [ String ] = [
        I18n . t ( "Zwiad ujawnia zasoby, flotę i rozwój planety." ) ,
        I18n . t ( "Wymagany okręt: %s. Zajmij wolną planetę lub przejmij niebronioną kolonię; limit kolonii: %d." ) % [ _catalog_name ( "colonizer" , "ships" ) , int ( state . get ( "limits" , { } ) . get ( "colonies" , 3 ) ) ] ,
        I18n . t ( "Atakuj obce kolonie lub graczy bez ochrony. Atak na gracza kończy twoją ochronę startową." ) ,
        I18n . t ( "Przewoź zasoby do własnych kolonii i sojuszników. Flota po dostawie wróci do bazy." ) ,
        I18n . t ( "Zwiadowca prowadzi poszukiwania. Transportowce zabierają znaleziska, a okręty bojowe chronią przed patrolem Roju." )
    ]
    mission_hint . text = captions [ mission_picker . selected ]
    if mission_picker . selected == 1 :
        mission_hint . text += "\n" + I18n . t ( FleetNavigationScript . Model . COLONIZATION_WARNING )
    if planetary_ui != null and planetary_ui . unknown_target ( selected_target ) :
        mission_hint . text = I18n . t ( "Nieznany cel. Najpierw wyślij zwiad." )
    if mission_picker . selected == 0 and not selected_scout_system . is_empty ( ) :
        mission_hint . text = I18n . t ( "Odśwież wolne planety i właścicieli w całym układzie. Szczegóły zasobów i obrony wymagają osobnego zwiadu planety." )
    var home_galaxy : String = str ( state . get ( "planet_galaxy_id" , "g1" ) )
    for system : Dictionary in state . get ( "galaxy" , [ ] ) :
        if str ( system . get ( "scout_target_id" , "" ) ) == selected_target and not selected_target . is_empty ( ) and str ( system . get ( "galaxy_id" , "g1" ) ) != home_galaxy and not megastructure_ui . using_tunnel ( ) :
            mission_hint . text += "\n" + I18n . t ( "Lot międzygalaktyczny — sprawdź koszt paliwa dla wybranej floty." )
        for planet : Dictionary in system . get ( "planets" , [ ] ) :
            if str ( planet . get ( "id" , "" ) ) == selected_target and str ( system . get ( "galaxy_id" , "g1" ) ) != home_galaxy and not megastructure_ui . using_tunnel ( ) :
                mission_hint . text += "\n" + I18n . t ( "Lot międzygalaktyczny — sprawdź koszt paliwa dla wybranej floty." )
                mission_hint . text += "\n" + _galaxy_name ( home_galaxy ) + " → " + _galaxy_name ( str ( system . get ( "galaxy_id" , "g1" ) ) )
    mission_hint . add_theme_color_override ( "font_color" , _ui_color ( Color ( "ffc56f" ) ) if mission_picker . selected == 2 else _ui_color ( Color ( "a0b3a4" ) ) )


func _fleet_value_changed ( _value : float ) -> void :
    if not refreshing :
        _invalidate_quote ( )


func _invalidate_quote ( reset_text : bool = true , draft_changed : bool = true ) -> void :
    if draft_changed :
        fleet_draft_generation += 1
    quote_ready = false
    preview_fingerprint = ""
    if send_button != null :
        send_button . disabled = true
    if reset_text and quote_label != null :
        quote_label . text = I18n . t ( "Sprawdź trasę, aby poznać czas lotu i koszt paliwa." )
        quote_label . add_theme_color_override ( "font_color" , _ui_color ( Color ( "a0b3a4" ) ) )

    if fleet_navigation != null :
        fleet_navigation . invalidate ( )


func _commit_fleet_inputs ( ) -> void :
    for key : String in _selectable_ship_keys ( ) :
        var spin : MobileQuantityScript = fleet_inputs [ key ]
        spin . apply ( )
    for key : String in RESOURCE_KEYS :
        var spin : MobileQuantityScript = cargo_inputs [ key ]
        spin . apply ( )


func _fleet_payload ( ) -> Dictionary :
    var ships : Dictionary = { }
    for key : String in _selectable_ship_keys ( ) :

        var spin : Variant = fleet_inputs . get ( key )
        ships [ key ] = int ( spin . value ) if is_instance_valid ( spin ) and spin is MobileQuantityScript else 0
    var payload : Dictionary = { "type" : "fleet" , "planet_id" : selected_planet , "mission" : MISSION_KEYS [ mission_picker . selected ] , "target_id" : selected_target , "ships" : ships }
    if mission_picker . selected == 0 and not selected_scout_system . is_empty ( ) :
        payload [ "scout_scope" ] = "system"
        payload [ "target_system_id" ] = selected_scout_system
    if mission_picker . selected != 4 and megastructure_ui != null and megastructure_ui . using_tunnel ( ) :
        payload [ "travel_mode" ] = "tunnel"
    if mission_picker . selected in [ 1 , 3 ] :
        var cargo : Dictionary = { }
        for key : String in RESOURCE_KEYS :
            var spin : Variant = cargo_inputs . get ( key )
            cargo [ key ] = int ( spin . value ) if is_instance_valid ( spin ) and spin is MobileQuantityScript else 0
        payload [ "cargo" ] = cargo
    if mission_picker . selected == 4 :
        payload [ "expedition_hours" ] = fleet_navigation.expedition_hours if fleet_navigation != null else 1
    return payload


func _fleet_fingerprint ( ) -> String :
    return JSON . stringify ( _fleet_payload ( ) )


func _quote_world_signature ( world : Dictionary ) -> String :
    var target : Dictionary = { }
    for system : Dictionary in world . get ( "galaxy" , [ ] ) :
        for planet : Dictionary in system . get ( "planets" , [ ] ) :
            if str ( planet . get ( "id" , "" ) ) == selected_target :
                target = { "id" : planet . get ( "id" , "" ) , "owner_type" : planet . get ( "owner_type" , "" ) , "owner_id" : planet . get ( "owner_id" , "" ) , "alliance_id" : planet . get ( "alliance_id" , "" ) , "protected_until" : planet . get ( "protected_until" , 0 ) , "is_home_planet" : planet . get ( "is_home_planet" , null ) }
    var navigation_stats : Array [ Dictionary ] = [ ]
    for entry : Dictionary in world . get ( "catalog" , { } ) . get ( "ships" , [ ] ) :
        navigation_stats . append ( { "key" : entry . get ( "key" , "" ) , "speed" : entry . get ( "effective_speed" , entry . get ( "speed" , 0 ) ) , "fuel" : entry . get ( "fuel" , 0 ) , "capacity" : entry . get ( "capacity" , 0 ) } )
    var mega : Dictionary = world . get ( "megastructures" , { } )
    var window : Dictionary = mega . get ( "window" , { } ) if mega . get ( "window" ) is Dictionary else { }
    var mission_slots : Array = [ ]
    for fleet : Dictionary in world . get ( "fleets" , [ ] ) :
        mission_slots . append ( [ fleet . get ( "id" , "" ) , fleet . get ( "mission" , "" ) , fleet . get ( "status" , "" ) ] )
    return JSON . stringify ( [ world . get ( "expeditions" , { } ) , mission_slots , world . get ( "own_planets" , [ ] ) . size ( ) , world . get ( "planet_id" , "" ) , world . get ( "buildings" , { } ) , world . get ( "research" , { } ) , world . get ( "ships" , { } ) , target , world . get ( "speed" , 1 ) , navigation_stats , mega . get ( "origin_id" , "" ) , window . get ( "id" , "" ) , window . get ( "closes_at" , 0 ) ] )


func _preview_fleet ( ) -> void :
    if update_required :
        return
    if request_pending :
        _notify ( I18n . t ( "Poczekaj na odpowiedź serwera i sprawdź trasę ponownie." ) , true )
        return
    _commit_fleet_inputs ( )
    if fleet_navigation != null and not fleet_navigation . draft_reason ( ) . is_empty ( ) :
        quote_label . text = I18n . t ( fleet_navigation . draft_reason ( ) )
        fleet_navigation . refresh ( )
        return
    if selected_target . is_empty ( ) :
        quote_label . text = I18n . t ( "Najpierw wybierz planetę docelową." )
        return
    _invalidate_quote ( false , false )
    quote_label . text = I18n . t ( "Sprawdzanie trasy…" )
    preview_requested_fingerprint = _fleet_fingerprint ( )
    preview_requested_world_signature = _quote_world_signature ( state )
    preview_requested_generation = fleet_draft_generation
    var payload : Dictionary = _fleet_payload ( )
    payload [ "allow_unaffordable" ] = true
    _request ( "/api/preview" , payload , "preview" )


func _send_fleet ( ) -> void :
    if update_required :
        return
    _commit_fleet_inputs ( )
    if not quote_ready or preview_fingerprint != _fleet_fingerprint ( ) :
        _invalidate_quote ( )
        return
    if request_pending :
        _notify ( I18n . t ( "Poczekaj na odpowiedź serwera i wyślij flotę ponownie." ) , true )
        return
    var payload : Dictionary = _fleet_payload ( )
    payload [ "request_id" ] = _new_request_id ( )
    _request ( "/api/action" , payload , "action" )
    _invalidate_quote ( false )
    quote_label . text = I18n . t ( "Wysyłanie rozkazu…" )


func _refresh_fleets ( ) -> void :
    if compact_ui != null :
        compact_ui . refresh_fleets ( )
        return
    var fleets : Array = state . get ( "fleets" , [ ] )
    var signature : String = JSON . stringify ( fleets )
    if signature == fleets_signature :
        return
    fleets_signature = signature
    _clear ( fleet_list )
    fleet_countdowns . clear ( )
    if fleets . is_empty ( ) :
        fleet_list . add_child ( _label ( I18n . t ( "Wszystkie floty są w bazach." ) , 21 , "94ab9a" ) )
    for fleet : Dictionary in fleets :
        var card : VBoxContainer = _card ( fleet_list )
        var mission : String = str ( fleet . get ( "mission" , "scout" ) )
        var index : int = MISSION_KEYS . find ( mission )
        var caption : String = I18n . t ( MISSION_NAMES [ index ] ) if index >= 0 else mission
        if str ( fleet . get ( "status" , "outbound" ) ) == "returning" :
            caption += I18n . t ( " • POWRÓT" )
        var fleet_art_key : String = str ( fleet . get ( "art_key" , "" ) )
        if not fleet_art_key . is_empty ( ) :
            _art_panel ( card , fleet_art_key , 150 )
        card . add_child ( _label ( caption , 23 , "edc77a" if fleet_art_key . begins_with ( "swarm/" ) else "91c89b" ) )
        var origin : String = str ( fleet . get ( "origin_name" , I18n . t ( "Baza" ) ) )
        var target : String = str ( fleet . get ( "target_name" , I18n . t ( "Cel" ) ) )
        var returning : bool = str ( fleet . get ( "status" , "outbound" ) ) == "returning"
        card . add_child ( _label ( "%s → %s" % [ target if returning else origin , origin if returning else target ] , 22 ) )
        card . add_child ( _label ( _ships_text ( fleet . get ( "ships" , { } ) , fleet . get ( "ship_names" , { } ) ) , 19 , "a0b3a4" ) )
        var countdown : Label = _label ( "" , 21 , "ffc56f" )
        card . add_child ( countdown )
        var progress : ProgressBar = _meter ( "edc77a" if fleet_art_key . begins_with ( "swarm/" ) else "91c89b" )
        progress . custom_minimum_size . y = 16
        progress . visible = float ( fleet . get ( "seconds" , 0 ) ) > 0
        card . add_child ( progress )
        fleet_countdowns . append ( { "label" : countdown , "bar" : progress , "seconds" : float ( fleet . get ( "seconds" , 0 ) ) , "at" : float ( fleet . get ( "arrives_at" , 0 ) ) } )
        var rare_cargo : int = int ( fleet . get ( "swarm_crystals" , 0 ) )
        if rare_cargo > 0 :
            var loot : HBoxContainer = _row ( card )
            loot . add_child ( _raster_icon ( "swarm/crystal" , 42 ) )
            loot . add_child ( _label ( I18n . t ( "%d kryształów Roju · w drodze do bazy" ) % rare_cargo , 22 , "edc77a" ) )


func _report_display_text ( report : Dictionary ) -> String :
    var raw : String = str ( report . get ( "text" , "" ) )
    var translated : String = I18n . t ( raw )
    if translated != raw or I18n . locale == "pl" :
        return translated



    if _server_text ( report . get ( "title" , "" ) ) == I18n . t ( "Narodziny cywilizacji" ) :
        for definition : Dictionary in _race_definitions ( ) :
            var race_name_source : String = str ( definition . get ( "name" , "" ) )
            var trait_source : String = str ( definition . get ( "trait" , "" ) )
            var tradeoff_source : String = str ( definition . get ( "tradeoff" , "" ) )
            var authored_suffix : String = " " + trait_source + " " + tradeoff_source
            if raw . ends_with ( authored_suffix ) and raw . contains ( race_name_source ) :
                var intro : String = I18n . t ( "Wybrano rasę: {0}. To stały wybór tego imperium." ) . format ( [ _server_text ( race_name_source ) ] )
                return intro + " " + _server_text ( trait_source ) + " " + _server_text ( tradeoff_source )
    return raw


func _refresh_reports ( ) -> void :
    if compact_ui != null :
        compact_ui . refresh_reports ( )
        return
    _refresh_report_scope ( )
    var reports : Array = state . get ( "reports" , [ ] )
    _update_unread_reports ( )
    var signature : String = JSON . stringify ( reports )
    if signature == reports_signature :
        return
    reports_signature = signature
    _clear ( report_list )
    if reports . is_empty ( ) :
        report_list . add_child ( _label ( I18n . t ( "Brak raportów. Wyślij zwiad, aby poznać sąsiednie planety." ) , 22 , "a0b3a4" ) )
    for report : Dictionary in reports :
        var card : VBoxContainer = _card ( report_list )
        var row : HBoxContainer = _row ( card )
        var kind_icon: TextureRect = TextureRect.new()
        kind_icon.texture = preload("res://client/scripts/report_summary.gd").icon_texture(report)
        kind_icon.custom_minimum_size = Vector2(48, 48)
        kind_icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
        kind_icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
        row.add_child(kind_icon)
        var title : VBoxContainer = VBoxContainer . new ( )
        title . size_flags_horizontal = Control . SIZE_EXPAND_FILL
        row . add_child ( title )
        title . add_child ( _label ( _server_text ( report . get ( "title" , I18n . t ( "Raport" ) ) ) , 25 , "ffc56f" ) )
        title . add_child ( _label ( _date ( float ( report . get ( "at" , 0 ) ) ) , 22 , "94ab9a" ) )
        if int ( report . get ( "swarm_crystals" , 0 ) ) > 0 :
            var loot : HBoxContainer = _row ( card )
            loot . add_child ( _raster_icon ( "swarm/crystal" , 34 ) )
            loot . add_child ( _label ( I18n . t ( "Kryształy Roju · %d" ) % int ( report [ "swarm_crystals" ] ) , 23 , "edc77a" ) )
        if report . has ( "scout" ) and report [ "scout" ] is Dictionary :
            var intel : Dictionary = report [ "scout" ]
            card . add_child ( ResourceInfo . label ( self , ReportResourceText . text ( self , report ) , 22 ) )
            _add_scout_summary ( card , intel )
            var scout_details : VBoxContainer = VBoxContainer . new ( )
            scout_details . add_theme_constant_override ( "separation" , 10 )
            _add_scout_data ( scout_details , intel )
            _details ( card , scout_details )
        else :
            _details ( card , ResourceInfo . label ( self , ReportResourceText . text ( self , report ) , 22 ) )


func _update_clock ( ) -> void :
    var now : float = _server_now ( )
    var idle: bool = not _ui_interacting()
    if idle and planned_queue_ui != null :
        planned_queue_ui . tick ( )
    if idle and megastructure_ui != null :
        megastructure_ui . tick ( )
    if idle and is_instance_valid ( research_tree ) and research_tree . visible :
        research_tree . update_clock ( )
    for index : int in range ( scout_age_labels . size ( ) - 1 , -1 , -1 ) :
        var scout_age : Dictionary = scout_age_labels [ index ]
        if not is_instance_valid ( scout_age [ "label" ] ) :
            scout_age_labels . remove_at ( index )
            continue
        var age_label : Label = scout_age [ "label" ]
        age_label . text = _scout_age_text ( float ( scout_age [ "at" ] ) )
    _refresh_incoming_clock ( now )
    _refresh_planet_protection ( )
    var time_dict : Dictionary = Time . get_datetime_dict_from_unix_time ( int ( now ) )
    var speed : float = float ( state . get ( "speed" , 1 ) )
    var clock_title : String = I18n . t ( "Czas" ) if is_equal_approx ( speed , 1.0 ) else I18n . t ( "Czas ×" ) + _number ( speed )
    clock_label . text = "%s • %02d:%02d:%02d UTC" % [ clock_title , int ( time_dict . get ( "hour" , 0 ) ) , int ( time_dict . get ( "minute" , 0 ) ) , int ( time_dict . get ( "second" , 0 ) ) ]
    var protection : float = float ( state . get ( "player" , { } ) . get ( "protected_until" , 0 ) ) - now
    protection_label . text = _duration ( protection ) if protection > 0 else I18n . t ( "Brak ochrony" )
    protection_label . add_theme_color_override ( "font_color" , _ui_color ( Color ( "91c89b" ) ) if protection > 0 else _ui_color ( Color ( "ff9287" ) ) )
    queue_bar . visible = queue_end > 0 and queue_duration > 0
    if queue_duration > 0 :
        queue_bar . value = clampf ( 100.0 * ( 1.0 - maxf ( 0.0 , queue_end - now ) / queue_duration ) , 0.0 , 100.0 )
    if idle and project_ui != null :
        project_ui . tick ( )
    if idle and planet_status != null :
        planet_status . tick ( )
    for item : Dictionary in fleet_countdowns :
        var label : Label = item [ "label" ]
        var remaining : float = float ( item [ "at" ] ) - now
        label . text = I18n . t ( "Dotarcie za " ) + _duration ( remaining ) if remaining > 0 else I18n . t ( "Rozliczanie misji…" )
        if item . has ( "bar" ) and float ( item . get ( "seconds" , 0 ) ) > 0 :
            var bar : ProgressBar = item [ "bar" ]
            bar . value = clampf ( 100.0 * ( 1.0 - maxf ( 0.0 , remaining ) / float ( item [ "seconds" ] ) ) , 0.0 , 100.0 )


func _new_request_id ( ) -> String :
    return Crypto . new ( ) . generate_random_bytes ( 16 ) . hex_encode ( )


func _server_now ( ) -> float :
    return server_stamp + float ( Time . get_ticks_msec ( ) - received_at_msec ) / 1000.0


func _duration ( seconds : float ) -> String :
    var total : int = maxi ( 0 , ceili ( seconds ) )
    var hours : int = total / 3600
    var minutes : int = ( total % 3600 ) / 60
    if hours > 0 :
        return I18n . t ( "%dh %02dmin" ) % [ hours , minutes ]
    if minutes > 0 :
        return I18n . t ( "%dmin %02ds" ) % [ minutes , total % 60 ]
    return I18n . t ( "%ds" ) % total


func _number ( value : float ) -> String :
    if absf ( value ) >= 1000000000 :
        return I18n . decimal ( I18n . t ( "%.1f mld" ) % ( value / 1000000000.0 ) )
    if absf ( value ) >= 1000000 :
        return I18n . decimal ( I18n . t ( "%.1f mln" ) % ( value / 1000000.0 ) )
    if absf ( value ) >= 10000 :
        return I18n . decimal ( ( "%.1f" % ( value / 1000.0 ) ) . trim_suffix ( ".0" ) ) + I18n . t ( " tys." )
    return str ( int ( value ) )


func _cost ( resources : Dictionary ) -> String :
    var segments : PackedStringArray = PackedStringArray ( )
    for key : String in RESOURCE_KEYS :
        var amount : float = float ( resources . get ( key , 0 ) )
        if amount > 0 :
            var short_name : String = I18n . t ( "metalu" ) if key == "metal" else I18n . t ( "kryształu" ) if key == "crystal" else I18n . t ( "paliwa" )
            segments . append ( "%s %s" % [ _number ( amount ) , short_name ] )
    return " · " . join ( segments ) if not segments . is_empty ( ) else I18n . t ( "Bez kosztu surowców" )


func _ships_text ( ships : Dictionary , names : Dictionary = { } ) -> String :
    var segments : PackedStringArray = PackedStringArray ( )
    for key : String in ships :
        var count : int = int ( ships . get ( key , 0 ) )
        if count > 0 :
            segments . append ( "%s ×%d" % [ _server_text ( names . get ( key , _catalog_name ( key , "ships" ) ) ) , count ] )
    return " · " . join ( segments )


func _date ( timestamp : float ) -> String :
    var value : Dictionary = Time . get_datetime_dict_from_unix_time ( int ( timestamp ) )
    return "%02d.%02d • %02d:%02d UTC" % [ int ( value . get ( "day" , 1 ) ) , int ( value . get ( "month" , 1 ) ) , int ( value . get ( "hour" , 0 ) ) , int ( value . get ( "minute" , 0 ) ) ]


func _clear ( node : Node ) -> void :
    for child : Node in node . get_children ( ) :
        node . remove_child ( child )
        child . queue_free ( )


func _skill_tree ( ) -> Dictionary :
    var value : Variant = state . get ( "skill_tree" , { } )
    return value if value is Dictionary else { }


func _skill_nodes ( ) -> Array [ Dictionary ] :
    var result : Array [ Dictionary ] = [ ]
    var supplied : Variant = _skill_tree ( ) . get ( "nodes" , [ ] )
    if supplied is Dictionary :
        supplied = supplied . values ( )
    if supplied is Array :
        for candidate : Variant in supplied :
            if candidate is Dictionary :
                result . append ( candidate )
    return result


func _skill_node ( id : String ) -> Dictionary :
    for node : Dictionary in _skill_nodes ( ) :
        if str ( node . get ( "id" , "" ) ) == id :
            return node
    return { }


func _skill_color ( race_id : String ) -> Color :
    return _ui_color ( Color ( "68b9ff" ) ) if race_id == "zetans" else _ui_color ( Color ( "ff6c63" ) ) if race_id == "automatons" else _ui_color ( Color ( "84dc86" ) ) if race_id == "symbionts" else _ui_color ( Color ( "edc77a" ) )


func _raster_icon ( key : String , width : float , height : float = 0.0 ) -> TextureRect :
    var icon : TextureRect = TextureRect . new ( )
    icon . texture = ArtLibrary . texture ( key )
    icon . custom_minimum_size = Vector2 ( width , height if height > 0 else width )
    icon . expand_mode = TextureRect . EXPAND_IGNORE_SIZE
    icon . stretch_mode = TextureRect . STRETCH_KEEP_ASPECT_CENTERED
    icon . size_flags_vertical = Control . SIZE_SHRINK_CENTER
    icon . mouse_filter = Control . MOUSE_FILTER_IGNORE
    return icon


func _make_skill_overlay ( ) -> void :
    skill_overlay = Control . new ( )
    skill_overlay . name = "SkillWheelOverlay"
    skill_overlay . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    skill_overlay . mouse_filter = Control . MOUSE_FILTER_STOP
    skill_overlay . visible = false
    add_child ( skill_overlay )
    var shade : ColorRect = ColorRect . new ( )
    shade . color = _ui_color ( Color ( "070c0c" ) )
    shade . mouse_filter = Control . MOUSE_FILTER_IGNORE
    shade . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    skill_overlay . add_child ( shade )
    skill_margin = MarginContainer . new ( )
    skill_margin . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    var sides : Array [ String ] = [ "left" , "top" , "right" , "bottom" ]
    for index : int in range ( sides . size ( ) ) :
        skill_margin . add_theme_constant_override ( "margin_" + sides [ index ] , mobile_insets [ index ] )
    skill_overlay . add_child ( skill_margin )
    var shell : VBoxContainer = VBoxContainer . new ( )
    shell . add_theme_constant_override ( "separation" , 6 )
    skill_margin . add_child ( shell )
    var heading : HBoxContainer = _row ( shell )
    var back : Button = _button ( I18n . t ( "‹ Wróć" ) , _close_skill_wheel )
    back . custom_minimum_size = Vector2 ( 110 , 64 )
    back . add_theme_font_size_override ( "font_size" , 22 )
    back . size_flags_horizontal = Control . SIZE_SHRINK_BEGIN
    heading . add_child ( back )
    heading . add_child ( _label ( I18n . t ( "Koło umiejętności" ) , 28 ) )
    var wallet_crystal : TextureRect = _raster_icon ( "swarm/crystal" , 44 )
    wallet_crystal . name = "SkillWheelCrystal"
    heading . add_child ( wallet_crystal )
    skill_wallet_label = _token_label ( "0" , 22 , "edc77a" )
    skill_wallet_label . tooltip_text = I18n . t ( "Kryształy Roju · łup dostępny po powrocie floty" )
    heading . add_child ( skill_wallet_label )
    var tools : HBoxContainer = _row ( shell )
    for race : Array in [ [ I18n . t ( "Zetanie" ) , "zetans" ] , [ I18n . t ( "Automatony" ) , "automatons" ] , [ I18n . t ( "Symbionci" ) , "symbionts" ] ] :
        var focus : Button = _button ( str ( race [ 0 ] ) , _focus_skill_race . bind ( str ( race [ 1 ] ) ) )
        focus . custom_minimum_size . y = 56
        focus . add_theme_font_size_override ( "font_size" , 21 )
        focus . add_theme_color_override ( "font_color" , _skill_color ( str ( race [ 1 ] ) ) )
        tools . add_child ( focus )
    var crystal_hint : Label = _label ( I18n . t ( "Walcz z Rojem Khar, aby zdobywać Kryształy Roju." ) , 22 , "c9d9cb" )
    crystal_hint . name = "SwarmCrystalHint"
    shell . add_child ( crystal_hint )
    skill_wheel = SkillWheelScript . new ( )
    skill_wheel . name = "SkillWheelCanvas"
    skill_wheel . custom_minimum_size . y = 280
    skill_wheel . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    skill_wheel . size_flags_vertical = Control . SIZE_EXPAND_FILL
    skill_wheel . connect ( "node_selected" , _select_skill_node )
    shell . add_child ( skill_wheel )
    var zoom : HBoxContainer = _row ( shell )
    var minus : Button = _button ( "−" , func ( ) -> void : skill_wheel . call ( "zoom_by" , 0.8 ) )
    var plus : Button = _button ( "+" , func ( ) -> void : skill_wheel . call ( "zoom_by" , 1.25 ) )
    var fit : Button = _button ( I18n . t ( "Całe koło" ) , func ( ) -> void : skill_wheel . call ( "fit_all" ) )
    for button : Button in [ minus , plus , fit ] :
        button . custom_minimum_size . y = 56
        zoom . add_child ( button )
    var detail : VBoxContainer = _card ( shell )
    detail . name = "SkillDetail"
    var detail_panel : PanelContainer = detail . get_parent ( ) as PanelContainer
    detail_panel . add_theme_stylebox_override ( "panel" , _style ( "101010" , "262626" , 18 , 12 ) )
    detail . add_theme_constant_override ( "separation" , 6 )
    var identity : HBoxContainer = _row ( detail )
    skill_detail_icon = SkillIconScript . make_preview ( "" , _ui_color ( Color ( "edc77a" ) ) , 64 )
    identity . add_child ( skill_detail_icon )
    skill_detail_title = _label ( I18n . t ( "Dotknij umiejętności" ) , 26 )
    skill_detail_title . size_flags_vertical = Control . SIZE_SHRINK_CENTER
    identity . add_child ( skill_detail_title )
    skill_detail_scroll = TouchScrollScript . new ( )
    skill_detail_scroll . name = "SkillDetailScroll"
    skill_detail_scroll . horizontal_scroll_mode = ScrollContainer . SCROLL_MODE_DISABLED
    skill_detail_scroll . custom_minimum_size . y = 96
    skill_detail_scroll . size_flags_vertical = Control . SIZE_FILL
    detail . add_child ( skill_detail_scroll )
    var description_body : VBoxContainer = VBoxContainer . new ( )
    description_body . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    description_body . add_theme_constant_override ( "separation" , 4 )
    skill_detail_scroll . add_child ( description_body )
    skill_detail_description = _label ( I18n . t ( "Walcz z Rojem Khar, aby zdobywać Kryształy Roju." ) , 22 , "c9d9cb" )
    description_body . add_child ( skill_detail_description )
    skill_detail_cost = _label ( "" , 22 , "edc77a" )
    description_body . add_child ( skill_detail_cost )
    skill_detail_status = _label ( "" , 20 , "a5d5ac" )
    description_body . add_child ( skill_detail_status )
    var action_row : HBoxContainer = _row ( detail )
    skill_unlock_button = _button ( I18n . t ( "Odblokuj" ) , _unlock_selected_skill , true )
    skill_unlock_button . custom_minimum_size . y = 76
    action_row . add_child ( skill_unlock_button )
    skill_retry_button = _button ( I18n . t ( "Odśwież" ) , _retry )
    skill_retry_button . custom_minimum_size . y = 76
    skill_retry_button . visible = false
    action_row . add_child ( skill_retry_button )
    var hunt : Button = _button ( I18n . t ( "Zdobądź kryształy Roju" ) , _hunt_swarm )
    hunt . name = "GetSwarmCrystals"
    hunt . custom_minimum_size . y = 56
    hunt . add_theme_font_size_override ( "font_size" , 22 )
    detail . add_child ( hunt )
    if is_instance_valid ( update_overlay ) :

        move_child ( update_overlay , get_child_count ( ) - 1 )


func _open_skill_wheel ( ) -> void :
    if update_required or showing_login or _needs_race_choice ( ) or _skill_nodes ( ) . is_empty ( ) :
        return
    if not is_instance_valid ( skill_overlay ) :
        _make_skill_overlay ( )
    if not skill_open and not skill_back_restore_pending :
        skill_previous_back_quit = get_tree ( ) . quit_on_go_back
    get_tree ( ) . quit_on_go_back = false
    skill_open = true
    skill_message = ""
    DisplayServer . virtual_keyboard_hide ( )
    var focused : Control = get_viewport ( ) . gui_get_focus_owner ( )
    if focused != null :
        focused . release_focus ( )
    _refresh_skills ( )
    _sync_screen_visibility ( )
    if skill_selected_id . is_empty ( ) :
        var own_race : String = str ( state . get ( "player" , { } ) . get ( "race_id" , "" ) )
        var roots : Dictionary = _skill_tree ( ) . get ( "roots" , { } )
        _select_skill_node ( str ( roots . get ( own_race , "" ) ) )
        skill_wheel . call_deferred ( "focus_race" , own_race )


func _close_skill_wheel ( ) -> void :
    _end_skill_navigation ( )
    _sync_screen_visibility ( )


func _end_skill_navigation ( ) -> void :
    if skill_open :
        skill_open = false
        skill_back_restore_pending = true
        _restore_skill_back_behavior . call_deferred ( )


func _restore_skill_back_behavior ( ) -> void :


    if not skill_open and skill_back_restore_pending :
        get_tree ( ) . quit_on_go_back = skill_previous_back_quit
        skill_back_restore_pending = false


func _focus_skill_race ( race_id : String ) -> void :
    skill_wheel . call ( "focus_race" , race_id )
    var roots : Dictionary = _skill_tree ( ) . get ( "roots" , { } )
    _select_skill_node ( str ( roots . get ( race_id , "" ) ) )


func _select_skill_node ( id : String ) -> void :
    if is_instance_valid ( skill_detail_scroll ) :
        skill_detail_scroll . scroll_vertical = 0
    skill_selected_id = id
    skill_message = ""
    if is_instance_valid ( skill_wheel ) :
        skill_wheel . call ( "select_node" , id )
    _refresh_skill_controls ( )


func _refresh_skills ( ) -> void :
    var nodes : Array [ Dictionary ] = _skill_nodes ( )
    var enabled : bool = not nodes . is_empty ( ) and not _needs_race_choice ( )
    if skill_open and not enabled :
        _close_skill_wheel ( )
    var amount : int = int ( state . get ( "player" , { } ) . get ( "swarm_crystals" , 0 ) )
    if compact_ui != null :
        compact_ui . update_wallet ( amount , enabled )
    else :
        skill_wallet_button . visible = enabled
        skill_wallet_button . text = I18n . t ( "Kryształy Roju · %s    Koło umiejętności ›" ) % _number ( amount )
        skill_wallet_button . icon = ArtLibrary . texture ( "swarm/crystal" ) if enabled else null
        skill_wallet_button . expand_icon = true
        skill_wallet_button . add_theme_constant_override ( "icon_max_width" , 32 )
        skill_entry . visible = enabled
    var learned : int = 0
    for node : Dictionary in nodes :
        if bool ( node . get ( "unlocked" , false ) ) :
            learned += 1
    var progression_hint : String = I18n . t ( "Wybieraj specjalizację. Każdy zakup podnosi ceny w całym kole." ) if _skill_tree ( ) . has ( "purchased_count" ) else I18n . t ( "Wybieraj specjalizację. Kryształy Roju otrzymasz po powrocie floty." )
    skill_entry_summary . text = I18n . t ( "%d / %d umiejętności · %s kryształów Roju\n%s" ) % [ learned , nodes . size ( ) , _number ( amount ) , progression_hint ]
    skill_hunt_button . disabled = update_required or showing_login or _needs_race_choice ( )
    if is_instance_valid ( skill_wheel ) :
        skill_wheel . call ( "set_tree" , _skill_tree ( ) )
        skill_wallet_label . text = _number ( amount )
        _refresh_skill_controls ( )


func _refresh_skill_controls ( ) -> void :
    if not is_instance_valid ( skill_detail_title ) :
        return
    var node : Dictionary = _skill_node ( skill_selected_id )
    var wallet : int = int ( state . get ( "player" , { } ) . get ( "swarm_crystals" , 0 ) )
    var cost : int = int ( node . get ( "cost" , 0 ) )
    var unlocked : bool = bool ( node . get ( "unlocked" , false ) )
    var available : bool = bool ( node . get ( "available" , false ) )
    var affordable : bool = bool ( node . get ( "affordable" , wallet >= cost ) )
    var pending_unlock : bool = str ( uncertain_action . get ( "type" , "" ) ) == "unlock_skill"
    skill_detail_title . text = _server_text ( node . get ( "name" , I18n . t ( "Dotknij umiejętności" ) ) )
    skill_detail_icon . set ( "icon" , str ( node . get ( "icon" , "" ) ) )
    skill_detail_icon . set ( "tint" , _skill_color ( str ( node . get ( "race_id" , node . get ( "race" , "" ) ) ) ) )
    skill_detail_description . text = _server_text ( node . get ( "description" , I18n . t ( "Walcz z Rojem Khar, aby zdobywać Kryształy Roju." ) ) )
    var effect_text : String = _server_text ( node . get ( "effect_text" , "" ) )
    if not effect_text . is_empty ( ) and not skill_detail_description . text . contains ( effect_text ) :
        skill_detail_description . text += "\n" + effect_text


    skill_detail_cost . text = I18n . t ( "Odblokowana" ) if unlocked else I18n . t ( "Koszt: %s kryształów Roju · posiadasz %s" ) % [ _exact_integer ( cost ) , _exact_integer ( wallet ) ]
    if not unlocked and _skill_tree ( ) . has ( "purchased_count" ) :
        skill_detail_cost . text += I18n . t ( "\nKażdy zakup podnosi koszt pozostałych umiejętności." )
    skill_detail_cost . visible = not node . is_empty ( )
    skill_unlock_button . text = I18n . t ( "Odblokowana" ) if unlocked else I18n . t ( "Potwierdzanie…" ) if pending_unlock else I18n . t ( "Odblokuj · %s" ) % _number ( cost )
    skill_unlock_button . disabled = node . is_empty ( ) or unlocked or not available or not affordable or request_pending or not uncertain_action . is_empty ( ) or session_token . is_empty ( ) or update_required
    skill_retry_button . visible = not uncertain_action . is_empty ( ) or not skill_message . is_empty ( )
    skill_retry_button . disabled = request_pending or update_required
    if not skill_message . is_empty ( ) :
        skill_detail_status . text = skill_message
    elif pending_unlock :
        skill_detail_status . text = I18n . t ( "Czekamy na potwierdzenie serwera. Odśwież ponawia ten sam zakup." )
    elif unlocked :
        skill_detail_status . text = I18n . t ( "Premia działa w całym imperium. Wybierz połączony węzeł." )
    elif not available and not node . is_empty ( ) :
        skill_detail_status . text = I18n . t ( "Najpierw odblokuj sąsiednią umiejętność połączoną linią." )
    elif not affordable :
        skill_detail_status . text = I18n . t ( "Brakuje %d kryształów. Zdobądź je w walce z Rojem i wróć flotą do bazy." ) % maxi ( 0 , cost - wallet )
    else :
        skill_detail_status . text = I18n . t ( "Zakup jest stały. Umiejętność działa w całym imperium." )
    skill_detail_status . visible = not node . is_empty ( ) or not skill_message . is_empty ( )


func _unlock_selected_skill ( ) -> void :
    var node : Dictionary = _skill_node ( skill_selected_id )
    var cost : int = int ( node . get ( "cost" , 0 ) )
    var wallet : int = int ( state . get ( "player" , { } ) . get ( "swarm_crystals" , 0 ) )
    if not skill_open or update_required or showing_login or session_token . is_empty ( ) or request_pending or not uncertain_action . is_empty ( ) :
        return
    if node . is_empty ( ) or bool ( node . get ( "unlocked" , false ) ) or not bool ( node . get ( "available" , false ) ) or wallet < cost :
        return
    skill_message = ""
    _request ( "/api/action" , { "type" : "unlock_skill" , "node_id" : skill_selected_id , "planet_id" : selected_planet , "request_id" : _new_request_id ( ) } , "action" )
    _refresh_skill_controls ( )


func _swarm_location ( ) -> Dictionary :
    return SwarmTargetScript . nearest ( state , selected_planet )


func _swarm_hunt_account_scope ( ) -> String :
    return BeginnerGuideScript . account_scope ( server_url , str ( state . get ( "player" , { } ) . get ( "id" , "" ) ) )


func _swarm_hunt_intro_seen ( scope : String ) -> bool :
    if scope . is_empty ( ) :
        return false
    var settings : ConfigFile = ConfigFile . new ( )
    return settings . load ( swarm_hunt_settings_path ) == OK and bool ( settings . get_value ( scope , "intro_seen" , false ) )


func _mark_swarm_hunt_intro_seen ( scope : String ) -> void :
    if scope . is_empty ( ) :
        return
    var settings : ConfigFile = ConfigFile . new ( )
    settings . load ( swarm_hunt_settings_path )
    settings . set_value ( scope , "intro_seen" , true )
    settings . save ( swarm_hunt_settings_path )


func _hunt_swarm ( ) -> void :
    if update_required or showing_login or _needs_race_choice ( ) or compact_ui == null :
        return
    if is_instance_valid ( update_overlay ) and update_overlay . visible :
        return
    var scope : String = _swarm_hunt_account_scope ( )
    if scope . is_empty ( ) :
        return
    swarm_hunt_generation += 1
    compact_ui . close_details ( )
    _close_skill_wheel ( )
    DisplayServer . virtual_keyboard_hide ( )
    var focused : Control = get_viewport ( ) . gui_get_focus_owner ( )
    if focused != null :
        focused . release_focus ( )
    _open_tab ( 1 )
    _show_full_galaxy_map ( false )


    _present_swarm_hunt . call_deferred ( swarm_hunt_generation , scope )


func _present_swarm_hunt ( generation : int , scope : String ) -> void :
    if generation != swarm_hunt_generation or scope != _swarm_hunt_account_scope ( ) :
        return
    if update_required or showing_login or _needs_race_choice ( ) or current_tab != 1 or not galaxy_overview . visible :
        return
    if is_instance_valid ( update_overlay ) and update_overlay . visible :
        return
    if skill_open or release_open or compact_ui . details_open ( ) or ( communications != null and communications . visible ) or ( alliance_ui != null and alliance_ui . visible ) :
        return

    var location : Dictionary = _swarm_location ( )
    if location . is_empty ( ) :
        _focus_home_system ( )
        _show_swarm_hunt_help ( { } )
        return
    selected_galaxy = str ( location [ "galaxy_id" ] )
    _choose_system ( str ( location [ "system_id" ] ) )
    galaxy_map . call ( "focus_system" , str ( location [ "system_id" ] ) , GalaxyMapScript . DEFAULT_FOCUS_ZOOM )
    _notify ( I18n . t ( "Rój: %s · układ %s" ) % [ location [ "planet_name" ] , location [ "system_name" ] ] )
    if not _swarm_hunt_intro_seen ( scope ) :
        _show_swarm_hunt_help ( location )
        if compact_ui . details_open ( ) :
            _mark_swarm_hunt_intro_seen ( scope )


func _show_swarm_hunt_help ( location : Dictionary ) -> void :
    var found : bool = not location . is_empty ( )
    var title : String = I18n . t ( "Zdobywanie Kryształów Roju" ) if found else I18n . t ( "Nie odkryto kolonii Roju Khar" )
    compact_ui . _begin_details ( title )
    var content : VBoxContainer = compact_ui . modal_body
    if found :
        var destination : HBoxContainer = _row ( content )
        destination . add_child ( _raster_icon ( "swarm/crystal" , 44 ) )
        var target : Label = _label ( I18n . t ( "Rój: %s · układ %s" ) % [ location [ "planet_name" ] , location [ "system_name" ] ] , 24 , "edc77a" )
        target . name = "SwarmHuntTarget"
        target . size_flags_vertical = Control . SIZE_SHRINK_CENTER
        destination . add_child ( target )
    var message : String = I18n . t ( "Otwórz zaznaczony układ i wybierz kolonię Roju Khar. Wyślij zwiad, aby sprawdzić jej obronę i zapas kryształów, a potem przygotuj najazd. Zdobyte kryształy otrzymasz po powrocie floty do bazy." ) if found else I18n . t ( "Wysyłaj zwiad do nieznanych układów lub rozbuduj obserwatorium, aby odnaleźć Rój Khar. Następnie ponownie wybierz „Zdobądź kryształy Roju”." )
    var explanation : Label = _label ( message , 24 , "c9d9cb" )
    explanation . name = "SwarmHuntExplanation"
    content . add_child ( explanation )
    var continue_button : Button = _button ( I18n . t ( "Pokaż na mapie" ) if found else I18n . t ( "Przeglądaj galaktykę" ) , compact_ui . close_details , true )
    continue_button . name = "SwarmHuntContinue"
    content . add_child ( continue_button )


func _scout_age_text ( at : float ) -> String :
    var minutes : int = maxi ( 0 , floori ( ( _server_now ( ) - at ) / 60.0 ) )
    return I18n . t ( "Ostatni zwiad: %d godz. %d min temu" ) % [ floori ( minutes / 60.0 ) , minutes % 60 ]


func _add_scout_summary ( parent : Node , intel : Dictionary ) -> void :
    var at : float = float ( intel . get ( "scouted_at" , 0.0 ) )
    var age : Label = _label ( _scout_age_text ( at ) , 23 , "edc77a" )
    parent . add_child ( age )
    scout_age_labels . append ( { "label" : age , "at" : at } )
    parent . add_child ( _label ( _server_text ( intel . get ( "swarm_activity" , "" ) ) , 23 , "c9d9cb" ) )


func _add_scout_data ( parent : Node , intel : Dictionary ) -> void :

    parent . add_child ( ResourceInfo . label ( self , ResourceInfo . cost ( self , intel . get ( "resources" , { } ) ) , 22 , "c9d9cb" ) )
    var loot : HBoxContainer = _row ( parent )
    loot . add_child ( _raster_icon ( "swarm/crystal" , 36 ) )
    loot . add_child ( _label ( I18n . t ( "Kryształy Roju · %d / %d" ) % [ int ( intel . get ( "swarm_crystals_stock" , 0 ) ) , int ( intel . get ( "swarm_crystals_capacity" , 6 ) ) ] , 22 , "edc77a" ) )
    parent . add_child ( _label ( I18n . t ( "Flota" ) , 23 ) )
    var units : Array = intel . get ( "swarm_units" , [ ] )
    if units . is_empty ( ) :
        parent . add_child ( _label ( I18n . t ( "Brak jednostek" ) , 22 , "a0b3a4" ) )
    for unit : Dictionary in units :
        parent . add_child ( _label ( "%s ×%d" % [ _server_text ( unit . get ( "name" , "" ) ) , int ( unit . get ( "count" , 0 ) ) ] , 22 , "c9d9cb" ) )
    parent . add_child ( _label ( I18n . t ( "Obrona planetarna" ) , 23 ) )
    for unit : Dictionary in intel . get ( "swarm_defenses" , [ ] ) :
        var unit_row : HBoxContainer = _row ( parent )
        unit_row . add_child ( _raster_icon ( _entry_art_key ( unit , str ( unit . get ( "key" , "" ) ) ) , 108 , 80 ) )
        unit_row . add_child ( _label ( "%s ×%d" % [ _server_text ( unit . get ( "name" , "" ) ) , int ( unit . get ( "count" , 0 ) ) ] , 22 , "c9d9cb" ) )
    parent . add_child ( _label ( I18n . t ( "Budowle Roju" ) , 23 ) )
    for building : Dictionary in intel . get ( "swarm_buildings" , [ ] ) :
        var building_row : HBoxContainer = _row ( parent )
        building_row . add_child ( _raster_icon ( str ( building . get ( "art_key" , "" ) ) , 108 , 80 ) )
        var caption : Label = _label ( I18n . t ( "%s · poz. %d" ) % [ _server_text ( building . get ( "name" , "" ) ) , int ( building . get ( "level" , 0 ) ) ] , 22 , "c9d9cb" )
        caption . size_flags_vertical = Control . SIZE_SHRINK_CENTER
        building_row . add_child ( caption )


func _swarm_planet_details ( card : VBoxContainer , planet : Dictionary ) -> void :
    var infested : Control = _art_panel ( card , "swarm/colony" , 190 )
    _art_caption ( infested ) . add_child ( _label ( I18n . t ( "Kolonia Roju" ) , 27 , "edc77a" ) )
    if not bool ( planet . get ( "has_scout" , false ) ) :
        card . add_child ( _label ( I18n . t ( "Brak rozpoznania" ) , 23 , "edc77a" ) )
        return
    _add_scout_summary ( card , planet )
    var details : VBoxContainer = VBoxContainer . new ( )
    details . add_theme_constant_override ( "separation" , 10 )
    _add_scout_data ( details , planet )
    _details ( card , details )


func _exact_integer ( value : int ) -> String :

    var digits : String = str ( value )
    var result : String = ""
    for index : int in range ( digits . length ( ) ) :
        if index > 0 and ( digits . length ( ) - index ) % 3 == 0 and digits [ index - 1 ] != "-" :
            result += " "
        result += digits [ index ]
    return result


func _unhandled_key_input ( event : InputEvent ) -> void :
    if skill_open and event . is_action_pressed ( "ui_cancel" ) :
        _close_skill_wheel ( )
        get_viewport ( ) . set_input_as_handled ( )


func _stat_number ( value : float ) -> String :


    return I18n . decimal ( String . num ( value , 2 ) . trim_suffix ( ".0" ) )


func _open_release_panel ( mode : String ) -> void :
    if update_required or request_pending :
        return
    if mode not in [ "account" , "help" , "attacks" ] or showing_login or session_token . is_empty ( ) :
        return
    if not is_instance_valid ( release_panel ) :
        release_panel = ReleasePanelScript . new ( )
        add_child ( release_panel )
        release_panel . configure ( self )
        release_panel . closed . connect ( _close_release_panel )
        release_panel . submitted . connect ( _submit_account_operation )
        release_panel . reauthentication_requested . connect ( _open_google_reauth )
        release_panel . defend_requested . connect ( _defend_planet )
    if not release_open and not release_back_restore_pending :
        release_previous_back_quit = get_tree ( ) . quit_on_go_back
    get_tree ( ) . quit_on_go_back = false
    release_open = true
    var focused : Control = get_viewport ( ) . gui_get_focus_owner ( )
    if focused != null :
        focused . release_focus ( )
    DisplayServer . virtual_keyboard_hide ( )
    var data : Dictionary = state . get ( "account" , { } ) . duplicate ( true )
    data [ "name" ] = str ( state . get ( "player" , { } ) . get ( "name" , I18n . t ( "Imperium" ) ) )
    data [ "attacks" ] = state . get ( "incoming_attacks" , [ ] )
    data [ "now" ] = _server_now ( )
    release_panel . show_mode ( mode , data )
    if is_instance_valid ( update_overlay ) :
        move_child ( update_overlay , get_child_count ( ) - 1 )
    _sync_screen_visibility ( )


func _close_release_panel ( sync : bool = true ) -> void :
    if is_instance_valid ( release_panel ) :
        release_panel . clear_private ( )
        release_panel . visible = false
    if release_open :
        release_open = false
        release_back_restore_pending = true
        _restore_release_back . call_deferred ( )
    DisplayServer . virtual_keyboard_hide ( )
    if sync and is_instance_valid ( login_screen ) and is_instance_valid ( app_screen ) :
        _sync_screen_visibility ( )


func _restore_release_back ( ) -> void :
    if not release_open and release_back_restore_pending :
        get_tree ( ) . quit_on_go_back = release_previous_back_quit
        release_back_restore_pending = false


func _submit_account_operation ( action : String , payload : Dictionary ) -> void :
    if action not in [ "logout-others" , "delete" ] :
        return
    if update_required or request_pending :
        _account_error ( I18n . t ( "Trwa łączenie. Spróbuj ponownie po odświeżeniu stanu." ) )
        return
    if session_token . is_empty ( ) :
        _account_error ( I18n . t ( "Zaloguj się ponownie przed zmianą ustawień konta." ) )
        return

    _request ( "/api/account/" + action , payload , "account:" + action )


func _account_error ( message : String ) -> void :
    if is_instance_valid ( release_panel ) :
        release_panel . set_busy ( false )
        if release_open :
            release_panel . set_status ( message , true )
            return
    _notify ( message , true )


func _on_account_response ( action : String , result : int , response_code : int , body : PackedByteArray ) -> void :
    if is_instance_valid ( release_panel ) :
        release_panel . set_busy ( false )
    if result != HTTPRequest . RESULT_SUCCESS or response_code >= 500 :
        _account_error ( I18n . t ( "Nie udało się potwierdzić wyniku. Operacja nie zostanie ponowiona automatycznie. Sprawdź połączenie i odśwież stan konta." ) )
        return
    var parsed : Variant = JSON . parse_string ( body . get_string_from_utf8 ( ) )
    if not parsed is Dictionary :
        _account_error ( I18n . t ( "Serwer zwrócił niepoprawną odpowiedź. Spróbuj ponownie po sprawdzeniu połączenia." ) )
        return
    var response : Dictionary = parsed
    if response_code == 426 :
        _close_release_panel ( )
        _handle_required_update ( response . get ( "update" ) )
        return
    if response_code == 401 and action != "recover" :
        session_token = ""
        _reset_world ( )
        _save_session ( )
        _set_login_mode ( "login" , false )
        _show_login ( I18n . t ( "Sesja wygasła. Zaloguj się ponownie." ) , true )
        return
    if response_code < 200 or response_code >= 300 or not bool ( response . get ( "ok" , false ) ) :
        _account_error ( I18n . t ( "Ta wersja serwera nie obsługuje jeszcze zarządzania kontem." ) if response_code == 404 else _server_text ( response . get ( "error" , I18n . t ( "Nie udało się zmienić ustawień konta." ) ) ) )
        return
    if action == "delete" :
        session_token = ""
        _reset_world ( )
        name_field . text = ""
        password_field . text = ""
        _set_login_mode ( "" , false )
        _save_session ( )
        _show_login ( _server_text ( response . get ( "message" , I18n . t ( "Konto i imperium zostały usunięte." ) ) ) )
        return
    if action == "recovery-code" :
        if release_open and release_panel . mode == "account" :
            release_panel . show_recovery_code ( str ( response . get ( "recovery_code" , "" ) ) )
        else :
            _notify ( I18n . t ( "Utworzono kod, ale ekran został zamknięty. W Konto możesz wygenerować nowy kod." ) )
        return
    if action in [ "password" , "recover" ] :
        var next_token : String = str ( response . get ( "token" , "" ) )
        if next_token . is_empty ( ) :
            _account_error ( I18n . t ( "Zmiana została przyjęta, ale nie otrzymano sesji. Zaloguj się nowym hasłem." ) )
            return
        if action == "recover" :
            _reset_world ( )
        session_token = next_token
        password_field . text = ""
        repeat_password_field . text = ""
        _save_session ( )
    if response . get ( "state" ) is Dictionary :
        _apply_state ( response [ "state" ] )
    var message : String = _server_text ( response . get ( "message" , I18n . t ( "Ustawienia konta zostały zapisane." ) ) )
    if action in [ "password" , "recover" ] :
        message += I18n . t ( " W Konto wygeneruj nowy kod odzyskiwania." )
    if release_open :
        release_panel . set_status ( message )
    else :
        _notify ( message )


func _refresh_release_state ( ) -> void :
    var onboarding : Dictionary = state . get ( "onboarding" , { } )
    var current : Variant = onboarding . get ( "current" )
    onboarding_card . visible = beginner_guide == null and current is Dictionary and not bool ( onboarding . get ( "finished" , false ) ) and not bool ( onboarding . get ( "skipped" , false ) )
    onboarding_resume . visible = beginner_guide == null and bool ( onboarding . get ( "skipped" , false ) ) and not bool ( onboarding . get ( "finished" , false ) )
    _refresh_onboarding_controls ( )
    if current is Dictionary :
        var completed : int = int ( onboarding . get ( "completed_count" , 0 ) )
        var total : int = maxi ( 1 , int ( onboarding . get ( "total" , 5 ) ) )
        onboarding_title . text = I18n . t ( "Pierwsze kroki · %d/%d" ) % [ completed , total ]
        onboarding_description . text = _server_text ( current . get ( "title" , I18n . t ( "Cel" ) ) ) + "\n" + _server_text ( current . get ( "description" , "" ) )
        onboarding_progress . value = float ( completed ) * 100.0 / total
        var action : String = str ( current . get ( "action" , "" ) )
        var destination : String = str ( current . get ( "target_id" , "" ) )
        onboarding_button . disabled = action not in [ "building" , "scout" , "hunt" , "skills" , "colonize" ] or ( action in [ "building" , "scout" , "hunt" , "colonize" ] and destination . is_empty ( ) )
        onboarding_button . text = I18n . t ( "Oczekiwanie" ) if onboarding_button . disabled else I18n . t ( "Przejdź" )
    var attacks : Array = state . get ( "incoming_attacks" , [ ] )
    incoming_banner . visible = not attacks . is_empty ( )
    _refresh_incoming_clock ( _server_now ( ) )
    var signature : String = JSON . stringify ( attacks )
    if signature != incoming_signature :
        incoming_signature = signature
        if release_open and release_panel . mode == "attacks" :
            release_panel . show_mode ( "attacks" , { "attacks" : attacks , "now" : _server_now ( ) } )


func _refresh_onboarding_controls ( ) -> void :
    if not is_instance_valid ( onboarding_skip ) :
        return
    onboarding_skip . disabled = request_pending or not uncertain_action . is_empty ( ) or update_required
    onboarding_resume . disabled = onboarding_skip . disabled


func _set_onboarding_skipped ( skipped : bool ) -> void :
    if request_pending or not uncertain_action . is_empty ( ) or update_required :
        return
    _request ( "/api/action" , { "type" : "skip_onboarding" if skipped else "resume_onboarding" , "planet_id" : selected_planet , "request_id" : _new_request_id ( ) } , "action" )


func _open_onboarding_target ( ) -> void :
    var step : Variant = state . get ( "onboarding" , { } ) . get ( "current" )
    if not step is Dictionary or onboarding_button . disabled :
        return
    var action : String = str ( step . get ( "action" , "" ) )
    var destination : String = str ( step . get ( "target_id" , "" ) )
    if action == "building" :
        _open_tab ( 0 )
        if building_rows . has ( destination ) :
            tabs [ 0 ] . call_deferred ( "ensure_control_visible" , building_rows [ destination ] [ "panel" ] )
    elif action == "skills" :
        _open_skill_wheel ( )
    elif action == "hunt" :
        _hunt_swarm ( )
    elif action in [ "scout" , "colonize" ] :
        _prepare_planet_mission ( destination , 1 if action == "colonize" else 0 )


func _refresh_incoming_clock ( now : float ) -> void :
    var attacks : Array = state . get ( "incoming_attacks" , [ ] )
    if not attacks . is_empty ( ) :
        var attack : Dictionary = attacks [ 0 ]
        var remaining : float = float ( attack . get ( "arrives_at" , 0 ) ) - now
        var mission_caption : String = I18n . t ( "PRZEJĘCIE · " ) if str ( attack . get ( "mission" , "" ) ) == "colonize" else I18n . t ( "ATAK · " )
        incoming_summary . text = mission_caption + str ( attack . get ( "target_name" , I18n . t ( "Kolonia" ) ) ) + "\n" + ( _duration ( remaining ) if remaining > 0 else I18n . t ( "Rozstrzyganie…" ) )
        if attacks . size ( ) > 1 :
            incoming_summary . text += I18n . t ( " · kolejne: %d" ) % ( attacks . size ( ) - 1 )
        incoming_summary . tooltip_text = str ( attack . get ( "attacker_name" , I18n . t ( "Przeciwnik" ) ) )
    if release_open and release_panel . mode == "attacks" :
        release_panel . update_attack_times ( now )


func _defend_planet ( planet_id : String ) -> void :
    if planet_id . is_empty ( ) or request_pending :
        return
    _close_release_panel ( )
    for index : int in range ( planet_picker . item_count ) :
        if str ( planet_picker . get_item_metadata ( index ) ) == planet_id :
            planet_picker . select ( index )
            _select_owned_planet ( index )
            _open_fleet_missions ( )
            tabs [ 2 ] . scroll_vertical = 0
            _notify ( I18n . t ( "Flota tej kolonii broni jej automatycznie. Możesz uzupełnić skład w stoczni lub przygotować lot." ) )
            return
    _notify ( I18n . t ( "Ta kolonia nie należy już do twojego imperium. Odśwież stan." ) , true )


func _report_identity ( report : Dictionary ) -> String :
    return str ( report . get ( "id" , JSON . stringify ( [ report . get ( "at" , 0 ) , report . get ( "title" , "" ) , report . get ( "text" , "" ) ] ) . sha256_text ( ) ) )


func _refresh_report_scope ( ) -> void :
    var owner_id : String = str ( state . get ( "player" , { } ) . get ( "id" , "" ) )
    var scope : String = ( server_url + "\n" + owner_id ) . sha256_text ( ) if not owner_id . is_empty ( ) else ""
    if scope == report_scope :
        return
    report_scope = scope
    report_read_ids . clear ( )
    reports_signature = ""
    if scope . is_empty ( ) :
        return
    var config : ConfigFile = ConfigFile . new ( )
    if config . load ( report_store_path ) == OK :
        var stored : Variant = config . get_value ( scope , "ids" , [ ] )
        if stored is Array :
            for id : Variant in stored :
                report_read_ids [ str ( id ) ] = true


func _mark_reports_read ( ) -> void :
    if state . is_empty ( ) :
        return
    _refresh_report_scope ( )
    var ids : Array = [ ]
    for report : Dictionary in state . get ( "reports" , [ ] ) :
        var id : String = _report_identity ( report )
        report_read_ids [ id ] = true
        ids . append ( id )
    if not report_scope . is_empty ( ) :
        var config : ConfigFile = ConfigFile . new ( )
        config . load ( report_store_path )
        config . set_value ( report_scope , "ids" , ids )
        config . save ( report_store_path )
    unread_reports = 0
    _refresh_report_badge ( )


func _update_unread_reports ( ) -> void :
    if current_tab == 4 and not showing_login and not release_open :
        _mark_reports_read ( )
        return
    unread_reports = 0
    for report : Dictionary in state . get ( "reports" , [ ] ) :
        if not report_read_ids . has ( _report_identity ( report ) ) :
            unread_reports += 1
    _refresh_report_badge ( )


func _refresh_report_badge ( ) -> void :
    if nav_buttons . size ( ) < 5 :
        return
    var caption : Label = nav_buttons [ 4 ] . get_meta ( "caption" ) as Label
    caption . text = I18n . t ( "Raporty" ) if unread_reports == 0 else I18n . t ( "Raporty · " ) + ( "9+" if unread_reports > 9 else str ( unread_reports ) )
    caption . add_theme_font_size_override ( "font_size" , 19 if unread_reports > 0 else 22 )
    nav_buttons [ 4 ] . tooltip_text = I18n . t ( "Nowe raporty: %d" ) % unread_reports if unread_reports > 0 else I18n . t ( "Raporty" )


func _start_play_update() -> void:
    var phase: String = str(PlayUpdates.status.get("state", "unsupported"))
    if phase == "downloaded":
        PlayUpdates.install()
    elif phase in ["unsupported", "unavailable", "error"]:
        _open_google_play_update()
    else:
        PlayUpdates.start()


func _sync_play_update() -> void:
    if not is_instance_valid(update_overlay):
        return
    var phase: String = str(PlayUpdates.status.get("state", "unsupported"))
    play_update_progress.visible = phase in ["downloading", "pending", "installing", "downloaded"]
    var total: int = int(PlayUpdates.status.get("total", 0))
    var downloaded: int = int(PlayUpdates.status.get("downloaded", 0))
    play_update_progress.value = 100.0 * downloaded / total if total > 0 else 0
    update_download_button.disabled = phase in ["checking", "pending", "downloading", "installing", "consent"]
    update_download_button.text = I18n.t("Zainstaluj i uruchom ponownie") if phase == "downloaded" else I18n.t("Otwórz Google Play") if phase in ["unsupported", "unavailable", "error"] else I18n.t("Pobierz aktualizację")
    if phase in ["downloading", "pending"]:
        update_status.text = I18n.t("Pobieranie aktualizacji…") + (" %.1f / %.1f MB" % [downloaded / 1048576.0, total / 1048576.0] if total > 0 else "")
    elif phase == "downloaded":
        play_update_progress.value = 100
        update_status.text = I18n.t("Zainstaluj aktualizację i uruchom grę ponownie.")
    elif phase == "installing":
        update_status.text = I18n.t("Instalowanie aktualizacji…")
