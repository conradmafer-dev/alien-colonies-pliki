extends RefCounted

const CatalogCardLayout = preload ( "res://client/scripts/catalog_card_layout.gd" )
const CatalogCardScript = preload ( "res://client/scripts/catalog_card.gd" )
const BattleReplayScript = preload ( "res://client/scripts/battle_replay.gd" )
const CatalogDetailsScript = preload ( "res://client/scripts/catalog_details.gd" )
const ResourceInfo = preload ( "res://client/scripts/resource_info.gd" )
const ReportSummary = preload ( "res://client/scripts/report_summary.gd" )
const ReportResourceText = preload ( "res://client/scripts/report_resource_text.gd" )
const BuildingTileEffectScript = preload ( "res://client/scripts/building_tile_effect.gd" )
const CatalogGuidanceScript = preload ( "res://client/scripts/catalog_guidance.gd" )
const FleetMissionTimelineScript = preload ( "res://client/scripts/fleet_mission_timeline.gd" )



var host
var battle_viewer
var modal : Control
var modal_close : Button
var modal_back_handler : Callable
var modal_missions : Button
var modal_margin : MarginContainer
var modal_body : VBoxContainer
var modal_scroll : ScrollContainer
var previous_back : bool = true
var mission_composer : VBoxContainer
var mission_overview : VBoxContainer
var composing : bool = false
var system_view : VBoxContainer
var race_button : Button
var fleet_empty : Label
var open_catalog_controls : Dictionary = { }
var open_catalog_action : Button
var open_catalog_signature : String = ""
var details_generation : int = 0
var details_keep_navigation : bool = false
var header_wallet_row : HBoxContainer
var header_wallet_title : Label
var header_wallet_amount : Label
var header_wallet_crystal : TextureRect
var header_fit_queued : bool = false
var galaxy_fit_queued : bool = false


func setup ( client : Control ) -> void :
    host = client
    _make_modal ( )
    _compact_header ( )
    _setup_planet ( )
    _setup_fleet ( )
    _setup_galaxy ( )

    host . fleet_header_art . get_parent ( ) . hide ( )
    host . research_header_art . get_parent ( ) . hide ( )
    host . skill_entry . hide ( )
    host . tabs [ 1 ] . resized . connect ( _queue_fit_map )
    host . tab_bodies [ 1 ] . minimum_size_changed . connect ( _queue_fit_map )
    sync_navigation ( )


func _make_modal ( ) -> void :
    modal = Control . new ( )
    modal . name = "ObjectDetailsOverlay"
    modal . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    modal . mouse_filter = Control . MOUSE_FILTER_STOP
    modal . z_index = 100
    modal . hide ( )
    host . add_child ( modal )
    host . resized . connect ( func ( ) -> void : _fit_modal_navigation . call_deferred ( ) )
    if not host . nav_buttons . is_empty ( ) :
        host . nav_buttons [ 0 ] . get_parent ( ) . resized . connect ( _fit_modal_navigation )
    var shade : ColorRect = ColorRect . new ( )
    shade . color = Color . BLACK
    shade . mouse_filter = Control . MOUSE_FILTER_IGNORE
    shade . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    modal . add_child ( shade )
    var margin : MarginContainer = MarginContainer . new ( )
    modal_margin = margin
    margin . mouse_filter = Control . MOUSE_FILTER_PASS
    margin . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    for side : String in [ "left" , "right" , "top" , "bottom" ] :
        margin . add_theme_constant_override ( "margin_" + side , 20 )
    modal . add_child ( margin )
    var layout : VBoxContainer = VBoxContainer . new ( )
    layout . mouse_filter = Control . MOUSE_FILTER_PASS
    layout . add_theme_constant_override ( "separation" , 10 )
    margin . add_child ( layout )
    var navigation : HBoxContainer = host . _row ( layout )
    navigation . name = "ObjectDetailsNavigation"
    modal_missions = host . _active_missions_shortcut ( 64 )
    modal_missions . name = "ActiveMissionsInDetails"
    modal_missions . hide ( )
    navigation . add_child ( modal_missions )
    var close : Button = host . _button ( I18n . t ( "Wstecz" ) , go_back )
    modal_close = close
    close . name = "CloseObjectDetails"
    close . custom_minimum_size . y = 64
    close . add_theme_font_size_override ( "font_size" , 22 )
    navigation . add_child ( close )
    modal_scroll = host . TouchScrollScript . new ( )
    modal_scroll . name = "ObjectDetailsScroll"
    modal_scroll . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    modal_scroll . size_flags_vertical = Control . SIZE_EXPAND_FILL
    modal_scroll . horizontal_scroll_mode = ScrollContainer . SCROLL_MODE_DISABLED
    modal_scroll . vertical_scroll_mode = ScrollContainer . SCROLL_MODE_AUTO
    modal_scroll . clip_contents = true
    modal_scroll . resized . connect ( _fit_details_art )
    layout . add_child ( modal_scroll )
    modal_body = VBoxContainer . new ( )
    modal_body . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    modal_body . size_flags_vertical = Control . SIZE_SHRINK_BEGIN
    modal_body . mouse_filter = Control . MOUSE_FILTER_PASS
    modal_body . add_theme_constant_override ( "separation" , 14 )
    modal_scroll . add_child ( modal_body )


func details_open ( ) -> bool :
    return is_instance_valid ( modal ) and modal . visible


func _begin_details ( title : String , keep_navigation : bool = false , show_missions : bool = false ) -> void :
    if host . update_required :
        return
    if is_instance_valid ( host . interaction_guard ) :
        host . interaction_guard . cancel_interaction ( )
    details_generation += 1
    modal_back_handler = Callable ( )
    if not details_open ( ) :
        previous_back = host . get_tree ( ) . quit_on_go_back
    host . get_tree ( ) . quit_on_go_back = false
    open_catalog_controls = { }
    open_catalog_action = null
    open_catalog_signature = ""
    if is_instance_valid ( battle_viewer ) : battle_viewer . shutdown ( )
    battle_viewer = null
    host . _clear ( modal_body )
    modal_missions . visible = show_missions
    if not title . is_empty ( ) :
        modal_body . add_child ( host . _label ( title , 30 ) )
    modal_scroll . scroll_vertical = 0
    if host . mobile_insets . x > 0 :
        for pair : Array in [ [ "left" , host . mobile_insets . x ] , [ "top" , host . mobile_insets . y ] , [ "right" , host . mobile_insets . z ] , [ "bottom" , host . mobile_insets . w ] ] :
            modal_margin . add_theme_constant_override ( "margin_" + str ( pair [ 0 ] ) , int ( pair [ 1 ] ) )
    details_keep_navigation = keep_navigation
    _fit_modal_navigation ( )
    modal . show ( )
    host . app_screen . process_mode = Node . PROCESS_MODE_INHERIT if keep_navigation else Node . PROCESS_MODE_DISABLED
    DisplayServer . virtual_keyboard_hide ( )
    modal_close . grab_focus ( )


func go_back ( ) -> void :
    if not details_open ( ) :
        return
    if modal_back_handler . is_valid ( ) and bool ( modal_back_handler . call ( ) ) :
        return
    close_details ( )


func close_details ( ) -> void :
    if not details_open ( ) :
        return
    if is_instance_valid ( host . interaction_guard ) :
        host . interaction_guard . cancel_interaction ( )
    modal . hide ( )
    modal_back_handler = Callable ( )
    details_keep_navigation = false
    modal . offset_bottom = 0

    host . app_screen . process_mode = Node . PROCESS_MODE_INHERIT
    details_generation += 1
    if is_instance_valid ( battle_viewer ) : battle_viewer . shutdown ( )
    open_catalog_controls = { }
    open_catalog_action = null
    open_catalog_signature = ""

    _restore_back . call_deferred ( )
    if host . fleet_navigation != null :
        host . fleet_navigation . refresh . call_deferred ( )


func _fit_modal_navigation ( ) -> void :
    if not is_instance_valid ( modal ) :
        return
    modal . offset_bottom = 0
    if details_keep_navigation and not host . nav_buttons . is_empty ( ) :
        var navigation : Control = host . nav_buttons [ 0 ] . get_parent ( )
        modal . offset_bottom = minf ( 0 , navigation . global_position . y - host . get_global_rect ( ) . end . y - 8 )
        modal_margin . add_theme_constant_override ( "margin_bottom" , 10 )


func _restore_back ( ) -> void :
    if is_instance_valid ( host ) and host . is_inside_tree ( ) and not details_open ( ) and not host . skill_open and not host . release_open and not ( host . communications != null and host . communications . visible ) :
        host . get_tree ( ) . quit_on_go_back = previous_back


func _details_art ( texture : Texture2D ) -> void :
    if texture == null :
        return
    var art : TextureRect = TextureRect . new ( )
    art . name = "DetailArtwork"
    art . texture = texture
    art . mouse_filter = Control . MOUSE_FILTER_IGNORE
    art . expand_mode = TextureRect . EXPAND_IGNORE_SIZE
    art . stretch_mode = TextureRect . STRETCH_KEEP_ASPECT_CENTERED
    art . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    art . resized . connect ( _fit_details_art )
    modal_body . add_child ( art )
    _fit_details_art ( )


func _fit_details_art ( ) -> void :
    if not is_instance_valid ( modal_scroll ) or not is_instance_valid ( modal_body ) :
        return


    var viewport_height : float = modal_scroll . size . y
    if viewport_height <= 0.0 :
        viewport_height = maxf ( 1.0 , host . size . y - 140.0 )
    var height_limit : float = maxf ( 1.0 , viewport_height * 0.35 )
    for node : Node in modal_body . get_children ( ) :
        if node is TextureRect and node . name == "DetailArtwork" and node . texture != null :
            var art : TextureRect = node as TextureRect
            var natural_height : float = art . size . x * float ( art . texture . get_height ( ) ) / maxf ( 1.0 , art . texture . get_width ( ) )
            var height : float = minf ( height_limit , maxf ( 96.0 , natural_height ) )
            if not is_equal_approx ( art . custom_minimum_size . y , height ) :
                art . custom_minimum_size . y = height


func _restore_details_scroll ( scroll_y : int ) -> void :
    var generation : int = details_generation
    var scene_tree : SceneTree = host . get_tree ( )


    await scene_tree . process_frame
    await scene_tree . process_frame
    if details_open ( ) and details_generation == generation :
        modal_scroll . scroll_vertical = scroll_y


func _copy_text ( node ) -> void :
    if not is_instance_valid ( node ) or str ( node . text ) . is_empty ( ) :
        return
    modal_body . add_child ( host . _label ( str ( node . text ) , 23 ) )


func _compact_header ( ) -> void :
    var brand : HBoxContainer = host . planet_picker . get_parent ( )
    brand . name = "CompactHeader"
    brand . size_flags_horizontal = Control . SIZE_SHRINK_BEGIN
    brand . size_flags_vertical = Control . SIZE_SHRINK_BEGIN
    brand . add_theme_constant_override ( "separation" , 8 )


    for child : Node in brand . get_children ( ) :
        if child is TextureRect :
            child . hide ( )


    host . connection_indicator . hide ( )
    host . connection_indicator . mouse_filter = Control . MOUSE_FILTER_IGNORE
    host . planet_picker . custom_minimum_size = Vector2 ( 96 , 64 )
    host . planet_picker . autowrap_mode = TextServer . AUTOWRAP_OFF
    host . planet_picker . clip_text = true
    host . planet_picker . add_theme_font_size_override ( "font_size" , 24 )
    host . skill_wallet_button . reparent ( brand )
    host . skill_wallet_button . custom_minimum_size = Vector2 ( 258 , 72 )
    host . skill_wallet_button . size_flags_horizontal = Control . SIZE_SHRINK_END
    host . skill_wallet_button . size_flags_vertical = Control . SIZE_SHRINK_CENTER
    host . skill_wallet_button . autowrap_mode = TextServer . AUTOWRAP_OFF
    host . skill_wallet_button . text = ""
    host . skill_wallet_button . icon = null
    host . skill_wallet_button . add_theme_stylebox_override ( "normal" , host . _style ( "000000" , "398fc5" , 15 , 10 ) )
    var wallet_margin : MarginContainer = MarginContainer . new ( )
    wallet_margin . name = "SkillWalletContent"
    wallet_margin . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    wallet_margin . mouse_filter = Control . MOUSE_FILTER_IGNORE
    for side : String in [ "left" , "right" ] :
        wallet_margin . add_theme_constant_override ( "margin_" + side , 14 )
    for side : String in [ "top" , "bottom" ] :
        wallet_margin . add_theme_constant_override ( "margin_" + side , 8 )
    host . skill_wallet_button . add_child ( wallet_margin )
    var wallet_content : HBoxContainer = HBoxContainer . new ( )
    wallet_content . mouse_filter = Control . MOUSE_FILTER_IGNORE
    wallet_content . add_theme_constant_override ( "separation" , 8 )
    wallet_margin . add_child ( wallet_content )
    header_wallet_title = host . _label ( I18n . t ( "Koło umiejętności" ) , 24 )
    header_wallet_title . name = "SkillWalletTitle"
    header_wallet_title . autowrap_mode = TextServer . AUTOWRAP_WORD
    header_wallet_title . size_flags_vertical = Control . SIZE_SHRINK_CENTER
    wallet_content . add_child ( header_wallet_title )
    header_wallet_crystal = host . _raster_icon ( "swarm/crystal" , 52 )
    header_wallet_crystal . name = "HeaderSwarmCrystal"
    wallet_content . add_child ( header_wallet_crystal )
    header_wallet_amount = host . _token_label ( "0" , 24 , "edc77a" )
    header_wallet_amount . name = "SkillWalletAmount"
    wallet_content . add_child ( header_wallet_amount )


    header_wallet_row = HBoxContainer . new ( )
    header_wallet_row . name = "CompactSkillWalletRow"
    header_wallet_row . size_flags_horizontal = Control . SIZE_SHRINK_BEGIN
    header_wallet_row . hide ( )
    var shell : VBoxContainer = brand . get_parent ( )
    shell . add_child ( header_wallet_row )
    shell . move_child ( header_wallet_row , brand . get_index ( ) + 1 )
    brand . resized . connect ( _queue_fit_header )
    brand . minimum_size_changed . connect ( _queue_fit_header )
    host . resized . connect ( _queue_fit_header )
    _queue_fit_header ( )
    _compact_resources ( )
    for button : Button in host . nav_buttons :
        button . custom_minimum_size . y = 80
    for body : VBoxContainer in host . tab_bodies :
        body . add_theme_constant_override ( "separation" , 10 )


func _compact_resources ( ) -> void :
    for key : String in host . RESOURCE_KEYS :
        var controls : Dictionary = host . resource_labels [ key ]
        var body : VBoxContainer = controls [ "rate" ] . get_parent ( )
        for child : Node in body . get_children ( ) :
            if child is Label and child != controls [ "rate" ] and child != controls . get ( "capacity" ) :
                child . hide ( )
        controls [ "count" ] . add_theme_font_size_override ( "font_size" , 24 )
        controls [ "rate" ] . add_theme_font_size_override ( "font_size" , 19 )
        body . get_parent ( ) . tooltip_text = I18n . t ( str ( host . RESOURCE_NAMES [ key ] ) ) . capitalize ( )


func _queue_fit_header ( ) -> void :
    if header_fit_queued or not is_instance_valid ( host ) :
        return
    header_fit_queued = true
    _fit_header . call_deferred ( )


func _header_text_width ( label : Label , text : String ) -> float :
    return ceilf ( label . get_theme_font ( "font" ) . get_string_size ( text , HORIZONTAL_ALIGNMENT_LEFT , -1 , label . get_theme_font_size ( "font_size" ) ) . x )


func _fit_header ( ) -> void :
    header_fit_queued = false
    if not is_instance_valid ( host ) or not is_instance_valid ( header_wallet_title ) :
        return
    var wallet : Button = host . skill_wallet_button
    var brand : HBoxContainer = host . planet_picker . get_parent ( )


    var available : float = maxf ( 1.0 , host . size . x - host . app_screen . get_theme_constant ( "margin_left" ) - host . app_screen . get_theme_constant ( "margin_right" ) )
    if not is_equal_approx ( brand . custom_minimum_size . x , available ) :
        brand . custom_minimum_size . x = available
        header_wallet_row . custom_minimum_size . x = available
    if not wallet . visible :
        header_wallet_row . hide ( )
        return
    var others : float = 0.0
    var other_count : int = 0
    for child : Node in brand . get_children ( ) :
        if child is Control and child != wallet and child . visible :
            others += child . get_combined_minimum_size ( ) . x
            other_count += 1
    var gap : float = brand . get_theme_constant ( "separation" )
    var fixed : float = 28.0 + 16.0 + header_wallet_crystal . custom_minimum_size . x + _header_text_width ( header_wallet_amount , header_wallet_amount . text )
    var title_width : float = _header_text_width ( header_wallet_title , header_wallet_title . text )
    var word_width : float = 0.0
    for word : String in header_wallet_title . text . split ( " " , false ) :
        word_width = maxf ( word_width , _header_text_width ( header_wallet_title , word ) )
    var max_wallet_width : float = available - others - other_count * gap
    var separate_row : bool = max_wallet_width < fixed + word_width
    var target_parent : HBoxContainer = header_wallet_row if separate_row else brand
    if wallet . get_parent ( ) != target_parent :
        wallet . reparent ( target_parent )
        wallet . size_flags_horizontal = Control . SIZE_EXPAND_FILL if separate_row else Control . SIZE_SHRINK_END
    header_wallet_row . visible = separate_row
    var target_width : float = available if separate_row else minf ( maxf ( 258.0 , fixed + title_width ) , max_wallet_width )
    var title_space : float = maxf ( word_width , target_width - fixed )


    var line_count : int = 1
    var line_width : float = 0.0
    var space_width : float = _header_text_width ( header_wallet_title , " " )
    for word : String in header_wallet_title . text . split ( " " , false ) :
        var next_width : float = _header_text_width ( header_wallet_title , word )
        if line_width > 0.0 and line_width + space_width + next_width > title_space :
            line_count += 1
            line_width = next_width
        else :
            line_width += ( space_width if line_width > 0.0 else 0.0 ) + next_width
    var line_height : float = header_wallet_title . get_theme_font ( "font" ) . get_height ( header_wallet_title . get_theme_font_size ( "font_size" ) )
    var line_spacing : float = header_wallet_title . get_theme_constant ( "line_spacing" )
    var target_size : Vector2 = Vector2 ( target_width , maxf ( 72.0 , ceilf ( line_height * line_count ) + line_spacing * ( line_count - 1 ) + 16.0 ) )
    if not wallet . custom_minimum_size . is_equal_approx ( target_size ) :
        wallet . custom_minimum_size = target_size


func _setup_planet ( ) -> void :
    host . colony_panorama . custom_minimum_size . y = 248
    host . queue_label . get_parent ( ) . get_parent ( ) . get_parent ( ) . hide ( )

    race_button = host . _button ( "" , _open_race )
    race_button . name = "CivilizationDetails"
    race_button . custom_minimum_size = Vector2 ( 96 , 96 )
    race_button . set_anchors_and_offsets_preset ( Control . PRESET_TOP_RIGHT )
    race_button . offset_left = -110
    race_button . offset_top = 14
    race_button . offset_right = -14
    race_button . offset_bottom = 110
    race_button . expand_icon = true
    race_button . add_theme_constant_override ( "icon_max_width" , 86 )
    host . colony_panorama . add_child ( race_button )


func _open_race ( ) -> void :
    _begin_details ( str ( host . race_name . text ) )
    _details_art ( host . race_colony . texture )
    _copy_text ( host . race_trait )
    _copy_text ( host . race_weapon )


func _setup_fleet ( ) -> void :
    var parent : VBoxContainer = host . fleet_missions_view
    var form_panel : Control = host . target_picker . get_parent ( ) . get_parent ( )
    mission_overview = VBoxContainer . new ( )
    mission_overview . name = "MissionsOverview"
    parent . add_child ( mission_overview )
    var create : Button = host . _button ( I18n . t ( "Nowa misja" ) , host . _start_new_mission , true )
    create . name = "NewMission"
    mission_overview . add_child ( create )
    create . hide ( )
    var expedition : Button = host . _button ( I18n . t ( "Ekspedycja" ) , func ( ) -> void : host.fleet_navigation.open_expedition() )
    expedition . name = "StartExpedition"
    expedition . custom_minimum_size . y = 64
    mission_overview . add_child ( expedition )
    for child : Node in parent . get_children ( ) :
        if child != form_panel and child != mission_overview :
            child . reparent ( mission_overview )
    mission_composer = VBoxContainer . new ( )
    mission_composer . name = "MissionComposer"
    parent . add_child ( mission_composer )
    var back : Button = host . _button ( I18n . t ( "Trwające misje" ) , close_composer )
    back . custom_minimum_size . y = 60
    mission_composer . add_child ( back )
    back . hide ( )
    form_panel . reparent ( mission_composer )
    fleet_empty = host . _label ( I18n . t ( "Brak statków na tej planecie. Zbuduj je w zakładce Budowa." ) , 22 )
    host . fleet_selection_list . add_child ( fleet_empty )
    for picker in [ host . target_picker , host . mission_picker ] :
        picker . custom_minimum_size . y = 68


func open_composer ( ) -> void :
    close_details ( )
    composing = true
    host . _set_fleet_mode ( 0 )
    host . _open_tab ( 2 )
    sync_navigation ( )
    if host . fleet_navigation != null :
        host . fleet_navigation . composer_opened ( )


func close_composer ( ) -> void :
    composing = false
    host . tabs [ 2 ] . scroll_vertical = 0
    sync_navigation ( )


func sync_navigation ( ) -> void :
    if not is_instance_valid ( mission_composer ) :
        return
    mission_composer . visible = composing
    mission_overview . visible = not composing
    host . fleet_action_bar . visible = host . current_tab == 2 and host . fleet_mode == 0 and composing
    host . fleet_mode_buttons [ 0 ] . text = I18n . t ( "Wstecz" ) if composing and host . fleet_mode == 0 else I18n . t ( "Nowa misja" )
    sync_galaxy ( )
    if host . fleet_navigation != null :
        host . fleet_navigation . refresh . call_deferred ( )


func _small_quantity ( quantity ) -> void :
    quantity . add_theme_constant_override ( "separation" , 4 )
    quantity . minus_button . custom_minimum_size = Vector2 ( 58 , 64 )
    quantity . plus_button . custom_minimum_size = Vector2 ( 58 , 64 )
    quantity . editor . custom_minimum_size = Vector2 ( 72 , 64 )
    quantity . editor . add_theme_font_size_override ( "font_size" , 22 )


func _compact_fleet ( ) -> void :
    var any_available : bool = false
    for key : String in host . fleet_selection_rows :
        var selection : Control = host . fleet_selection_rows [ key ]
        var quantity = host . fleet_inputs [ key ]
        var count : int = int ( host . state . get ( "ships" , { } ) . get ( key , 0 ) )
        quantity . max_value = count
        if count == 0 :
            quantity . value = 0
        selection . visible = count > 0
        any_available = any_available or count > 0
        if not selection . has_meta ( "compact" ) :
            selection . set_meta ( "compact" , true )
            var row : HBoxContainer = selection . get_child ( 0 )
            quantity . reparent ( row )
            _small_quantity ( quantity )
            host . fleet_portraits [ key ] . custom_minimum_size = Vector2 ( 76 , 62 )
            host . fleet_names [ key ] . add_theme_font_size_override ( "font_size" , 20 )
            host . fleet_available [ key ] . add_theme_font_size_override ( "font_size" , 22 )
    fleet_empty . visible = not any_available


func _setup_galaxy ( ) -> void :
    var body : VBoxContainer = host . tab_bodies [ 1 ]
    system_view = VBoxContainer . new ( )
    system_view . name = "SelectedSystemView"
    body . add_child ( system_view )
    for node in [ host . system_picker . get_parent ( ) , host . system_heading , host . system_coordinates , host . planet_list ] :
        node . reparent ( system_view )


    var info : Button = host . _button ( "i" , _open_galaxy_details )
    info . custom_minimum_size = Vector2 ( 60 , 60 )
    info . size_flags_horizontal = Control . SIZE_SHRINK_END
    host . galaxy_toggle . get_parent ( ) . add_child ( info )
    host . galaxy_summary . hide ( )
    host . galaxy_travel_note . hide ( )
    host . galaxy_picker . custom_minimum_size . y = 64
    host . previous_galaxy_button . custom_minimum_size . y = 64
    host . next_galaxy_button . custom_minimum_size . y = 64
    for node : Node in host . galaxy_overview . get_children ( ) :
        if node is HBoxContainer :
            for button : Node in node . get_children ( ) :
                if button is Button :
                    button . custom_minimum_size . y = 56
    sync_galaxy ( )


func _open_galaxy_details ( ) -> void :
    _begin_details ( host . _galaxy_name ( host . selected_galaxy ) )
    _copy_text ( host . galaxy_summary )
    _copy_text ( host . galaxy_travel_note )
    host . planetary_ui . add_observation_help ( modal_body )


func sync_galaxy ( ) -> void :
    if not is_instance_valid ( system_view ) :
        return
    system_view . visible = not host . galaxy_overview . visible
    host . galaxy_picker . get_parent ( ) . visible = host . galaxy_overview . visible
    host . system_picker . get_parent ( ) . hide ( )
    host . tabs [ 1 ] . vertical_scroll_mode = ScrollContainer . SCROLL_MODE_DISABLED if host . galaxy_overview . visible else ScrollContainer . SCROLL_MODE_AUTO
    _queue_fit_map ( )


func _queue_fit_map ( ) -> void :
    if galaxy_fit_queued or not is_instance_valid ( host ) :
        return
    # Labels and the legend settle after the tab's first resize. Refit when
    # their minimum size changes so both galaxy entry points keep the same
    # map scale instead of using an early, undersized viewport.
    galaxy_fit_queued = true
    _fit_map . call_deferred ( )


func _fit_map ( ) -> void :
    galaxy_fit_queued = false
    if not is_instance_valid ( host ) or not is_instance_valid ( system_view ) or not host . galaxy_overview . visible :
        return

    var used : float = 32.0
    for node : Node in host . tab_bodies [ 1 ] . get_children ( ) :
        if node is Control and node . visible and node != host . galaxy_overview :
            used += node . get_combined_minimum_size ( ) . y + 10.0
    for node : Node in host . galaxy_overview . get_children ( ) :
        if node is Control and node . visible and node != host . galaxy_map :
            used += node . get_combined_minimum_size ( ) . y + 4.0
    var height : float = maxf ( 140.0 , host . tabs [ 1 ] . size . y - used )
    if absf ( host . galaxy_map . custom_minimum_size . y - height ) > 1.0 :
        host . galaxy_map . custom_minimum_size . y = height


func compact_catalog ( controls : Dictionary ) -> void :
    if controls . has ( "compact" ) :
        _update_building_effect ( controls )
        _update_catalog_guidance ( controls )
        return
    if str ( controls [ "kind" ] ) in [ "build" , "ship" , "defense" ] :
        _carousel_catalog ( controls )
        return
    controls [ "compact" ] = true
    var panel : PanelContainer = controls [ "panel" ]
    var card : VBoxContainer = panel . get_child ( 0 )
    card . add_theme_constant_override ( "separation" , 6 )
    var originals : Array [ Node ] = card . get_children ( )
    var extra : VBoxContainer = VBoxContainer . new ( )
    extra . name = "FullDetailsData"
    extra . hide ( )
    card . add_child ( extra )
    for node : Node in originals :
        node . reparent ( extra )
    var row : HBoxContainer = host . _row ( card )
    var picture : Control = controls [ "art" ] . get_parent ( )
    picture . reparent ( row )



    picture . custom_minimum_size = Vector2 ( 224 , 261 if str ( controls [ "kind" ] ) == "build" else 188 )
    picture . size_flags_horizontal = Control . SIZE_SHRINK_BEGIN
    picture . size_flags_vertical = Control . SIZE_FILL
    picture . mouse_filter = Control . MOUSE_FILTER_PASS
    for node : Node in picture . get_children ( ) :
        if node != controls [ "art" ] and node is Control :
            node . hide ( )
    var information : VBoxContainer = VBoxContainer . new ( )
    information . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    information . add_theme_constant_override ( "separation" , 8 )
    row . add_child ( information )
    controls [ "heading" ] . reparent ( information )
    controls [ "heading" ] . add_theme_font_size_override ( "font_size" , 23 )
    controls [ "level" ] . reparent ( information )
    controls [ "level" ] . add_theme_font_size_override ( "font_size" , 19 )
    controls [ "role" ] . reparent ( information )
    controls [ "role" ] . add_theme_font_size_override ( "font_size" , 19 )
    var prices : Control = controls [ "costs" ] [ "metal" ] [ "row" ] . get_parent ( )
    prices . reparent ( information )
    prices . add_theme_constant_override ( "h_separation" , 12 )
    for key : String in host . RESOURCE_KEYS :
        controls [ "costs" ] [ key ] [ "amount" ] . add_theme_font_size_override ( "font_size" , 20 )
    if str ( controls [ "kind" ] ) == "build" :
        var effect : Label = host . _label ( "" , 20 , "bad4c3" )
        effect . name = "BuildingTileEffect"
        effect . add_theme_font_size_override ( "font_size" , 20 )
        effect . max_lines_visible = -1
        effect . text_overrun_behavior = TextServer . OVERRUN_NO_TRIMMING
        information . add_child ( effect )


        effect . resized . connect ( _fit_building_effect . bind ( effect ) )
        controls [ "tile_effect" ] = effect
        _update_building_effect ( controls )


    var spacer : Control = Control . new ( )
    spacer . size_flags_vertical = Control . SIZE_EXPAND_FILL
    spacer . mouse_filter = Control . MOUSE_FILTER_IGNORE
    information . add_child ( spacer )
    if controls [ "amount" ] != null :
        controls [ "amount" ] . reparent ( information )
        _small_quantity ( controls [ "amount" ] )
    var actions : HBoxContainer = host . _row ( information )
    controls [ "time" ] . reparent ( actions )
    controls [ "time" ] . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    controls [ "time" ] . size_flags_vertical = Control . SIZE_FILL
    controls [ "time" ] . vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
    controls [ "time" ] . add_theme_font_size_override ( "font_size" , 19 )
    controls [ "action" ] . reparent ( actions )
    controls [ "action" ] . custom_minimum_size = Vector2 ( 144 , 64 )
    controls [ "action" ] . add_theme_font_size_override ( "font_size" , 22 )
    controls [ "reason" ] . reparent ( card )
    controls [ "reason" ] . add_theme_font_size_override ( "font_size" , 19 )
    _update_catalog_guidance ( controls )


    panel . set_script ( CatalogCardScript )
    panel . set_process_input ( false )
    panel . set ( "excluded_controls" , [ controls [ "action" ] , controls [ "amount" ] ] )
    panel . mouse_filter = Control . MOUSE_FILTER_PASS
    panel . focus_mode = Control . FOCUS_ALL
    panel . mouse_default_cursor_shape = Control . CURSOR_POINTING_HAND
    panel . tooltip_text = I18n . t ( "Opis i wymagania" )
    panel . connect ( "details_requested" , _open_catalog . bind ( controls ) )


func _carousel_catalog ( controls : Dictionary ) -> void :
    controls [ "compact" ] = true
    controls [ "carousel" ] = true
    var panel : PanelContainer = controls [ "panel" ]
    var card : VBoxContainer = panel . get_child ( 0 )
    var originals : Array [ Node ] = card . get_children ( )
    var extra : VBoxContainer = VBoxContainer . new ( )
    extra . name = "FullDetailsData"
    extra . hide ( )
    card . add_child ( extra )
    for node : Node in originals :
        node . reparent ( extra )
    var layout : Dictionary = CatalogCardLayout . create ( host , panel , card )
    var content : VBoxContainer = layout [ "content" ]
    var footer : VBoxContainer = layout [ "footer" ]
    controls [ "content_scroll" ] = layout [ "scroll" ]
    var picture : Control = controls [ "art" ] . get_parent ( )
    picture . reparent ( content )
    picture . custom_minimum_size = Vector2 ( 0 , 240 )
    picture . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    picture . mouse_filter = Control . MOUSE_FILTER_PASS
    CatalogCardLayout . fit_art ( panel , picture )
    for node : Node in picture . get_children ( ) :
        if node != controls [ "art" ] and node is Control :
            node . hide ( )
    controls [ "heading" ] . reparent ( content )
    controls [ "heading" ] . add_theme_font_size_override ( "font_size" , 28 )
    if str ( controls [ "kind" ] ) in [ "ship" , "defense" ] :


        var inventory : PanelContainer = PanelContainer . new ( )
        inventory . name = "FleetAtBaseBadge"
        inventory . mouse_filter = Control . MOUSE_FILTER_PASS
        inventory . add_theme_stylebox_override ( "panel" , host . _style ( "000000" , "91c89b" , 12 , 10 ) )
        footer . add_child ( inventory )
        controls [ "level" ] . reparent ( inventory )
        controls [ "level" ] . add_theme_font_size_override ( "font_size" , 30 )
        controls [ "level" ] . horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
        controls [ "level" ] . custom_minimum_size . y = 40
    else :
        controls [ "level" ] . reparent ( content )
        controls [ "level" ] . add_theme_font_size_override ( "font_size" , 22 )
    controls [ "badge" ] . reparent ( content )
    controls [ "badge" ] . add_theme_font_size_override ( "font_size" , 20 )
    controls [ "role" ] . reparent ( content )
    controls [ "role" ] . name = "CatalogPurpose"
    controls [ "role" ] . add_theme_font_size_override ( "font_size" , 23 )
    controls [ "role" ] . max_lines_visible = -1
    controls [ "role" ] . text_overrun_behavior = TextServer . OVERRUN_NO_TRIMMING
    if str ( controls [ "kind" ] ) == "build" :
        var effect : Label = host . _label ( "" , 22 , "bad4c3" )
        effect . name = "BuildingTileEffect"
        effect . max_lines_visible = -1
        effect . text_overrun_behavior = TextServer . OVERRUN_NO_TRIMMING
        content . add_child ( effect )
        effect . resized . connect ( _fit_building_effect . bind ( effect ) )
        controls [ "tile_effect" ] = effect
        _update_building_effect ( controls )
    else :
        controls [ "stats" ] . reparent ( content )
        controls [ "stats" ] . visible = true
        var traits : Label = host . _label ( "" , 21 , "bad4c3" )
        traits . name = "ShipTraits"
        content . add_child ( traits )
        controls [ "ship_traits" ] = traits
    var requirements : Label = host . _label ( "" , 20 , "a0b3a4" )
    requirements . name = "CardRequirements"
    content . add_child ( requirements )
    controls [ "carousel_requirements" ] = requirements
    controls [ "reason" ] . reparent ( content )
    controls [ "reason" ] . add_theme_font_size_override ( "font_size" , 21 )
    for extra_key : String in [ "batch_effect" , "production_effect" , "refund" , "progress_panel" ] :
        controls [ extra_key ] . reparent ( content )
    var prices : Control = controls [ "costs" ] [ "metal" ] [ "row" ] . get_parent ( )
    prices . reparent ( footer )
    prices . add_theme_constant_override ( "h_separation" , 22 )
    for key : String in host . RESOURCE_KEYS :
        controls [ "costs" ] [ key ] [ "amount" ] . add_theme_font_size_override ( "font_size" , 23 )
    if controls [ "amount" ] != null :
        var quantity_row : HBoxContainer = host . _row ( footer )
        var quantity_label : Label = host . _label ( I18n . t ( "Zamawiane jednostki" ) if str ( controls [ "kind" ] ) == "defense" else I18n . t ( "Zamawiane statki" ) , 20 , "a0b3a4" )
        quantity_label . size_flags_vertical = Control . SIZE_SHRINK_CENTER
        quantity_row . add_child ( quantity_label )
        controls [ "amount" ] . reparent ( quantity_row )
        _small_quantity ( controls [ "amount" ] )
        controls [ "amount" ] . size_flags_horizontal = Control . SIZE_SHRINK_END
    var actions : HBoxContainer = host . _row ( footer )
    controls [ "time" ] . reparent ( actions )
    controls [ "time" ] . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    controls [ "time" ] . size_flags_vertical = Control . SIZE_SHRINK_CENTER
    controls [ "time" ] . add_theme_font_size_override ( "font_size" , 23 )
    controls [ "action" ] . reparent ( actions )
    controls [ "action" ] . custom_minimum_size = Vector2 ( 220 , 72 )
    controls [ "action" ] . add_theme_font_size_override ( "font_size" , 25 )
    _update_catalog_guidance ( controls )


    panel . mouse_filter = Control . MOUSE_FILTER_PASS
    panel . focus_mode = Control . FOCUS_NONE
    panel . mouse_default_cursor_shape = Control . CURSOR_ARROW
    panel . tooltip_text = ""


func _update_building_effect ( controls : Dictionary ) -> void :
    if not controls . has ( "tile_effect" ) :
        return
    var label : Label = controls [ "tile_effect" ]
    label . text = CatalogGuidanceScript . building_effect ( host , controls . get ( "entry" , { } ) )
    if label . text . is_empty ( ) :
        label . text = BuildingTileEffectScript . text ( host , controls . get ( "entry" , { } ) )
    label . visible = not label . text . is_empty ( )
    _fit_building_effect . call_deferred ( label )


func _fit_building_effect ( label : Label ) -> void :
    if not is_instance_valid ( label ) :
        return
    var lines : int = maxi ( label . get_line_count ( ) , 1 )
    var height : float = ceilf ( label . get_theme_font ( "font" ) . get_height ( label . get_theme_font_size ( "font_size" ) ) ) * lines
    height += label . get_theme_constant ( "line_spacing" ) * ( lines - 1 )
    if label . custom_minimum_size . y != height :
        label . custom_minimum_size . y = height


func _update_catalog_guidance ( controls : Dictionary ) -> void :
    var entry : Dictionary = controls . get ( "entry" , { } )
    var kind : String = str ( controls . get ( "kind" , "build" ) )
    var amount : int = int ( controls [ "amount" ] . value ) if controls . get ( "amount" ) != null else 1
    if kind == "build" :
        var role : Label = controls [ "role" ]
        if bool ( controls . get ( "carousel" , false ) ) :
            role . text = "\n" . join ( CatalogDetailsScript . description_paragraphs ( host , entry , kind , false ) )
        else :
            role . text = CatalogGuidanceScript . role ( entry , kind )
        role . visible = not role . text . is_empty ( )
    if controls . has ( "ship_traits" ) :
        var traits : Label = controls [ "ship_traits" ]
        traits . text = "\n" . join ( CatalogDetailsScript . unit_traits ( host , entry ) )
        traits . visible = not traits . text . is_empty ( )
    if controls . has ( "carousel_requirements" ) :
        var requirements : Label = controls [ "carousel_requirements" ]
        var lines : PackedStringArray = PackedStringArray ( )
        var seen : Dictionary = { }
        var all_met : bool = true
        for requirement : Dictionary in entry . get ( "requirements" , [ ] ) :
            var group : String = str ( requirement . get ( "group" , "buildings" ) )
            var key : String = str ( requirement . get ( "key" , "" ) )
            var identity : String = group + ":" + key
            if seen . has ( identity ) :
                continue
            seen [ identity ] = true
            var current : int = int ( requirement . get ( "current" , host . state . get ( group , { } ) . get ( key , 0 ) ) )
            var required : int = int ( requirement . get ( "level" , 0 ) )
            var met : bool = bool ( requirement . get ( "met" , current >= required ) )
            all_met = all_met and met
            lines . append ( ( "✓ " if met else "○ " ) + host . _server_text ( requirement . get ( "name" , key ) ) + " %d/%d" % [ current , required ] )
        requirements . text = I18n . t ( "Wymagania" ) + ": " + " · " . join ( lines )
        requirements . visible = not lines . is_empty ( )
        requirements . add_theme_color_override ( "font_color" , host . _ui_color ( Color ( "a0b3a4" if all_met else "edc77a" ) ) )
    var reason : Label = controls [ "reason" ]
    reason . text = CatalogGuidanceScript . explanation ( host , entry , amount , kind , not controls . has ( "carousel_requirements" ) )
    reason . visible = not reason . text . is_empty ( )


func _open_catalog ( controls : Dictionary ) -> void :
    if host . update_required or not is_instance_valid ( controls . get ( "panel" ) ) :
        return
    var catalog_key : String = str ( controls . get ( "entry" , { } ) . get ( "key" , "" ) )
    if str ( controls . get ( "kind" , "" ) ) == "research" and host . research_tree != null and host . research_tree . entries . has ( catalog_key ) :
        host . research_tree . open_details ( catalog_key )
        return
    _begin_details ( str ( controls [ "heading" ] . text ) )
    open_catalog_controls = controls
    open_catalog_signature = _catalog_signature ( controls )
    _details_art ( controls [ "art" ] . texture )
    open_catalog_action = host . _button ( "" , host . _catalog_action . bind ( str ( controls [ "kind" ] ) , catalog_key ) , true )
    open_catalog_action . name = "CatalogDetailsAction"
    modal_body . add_child ( open_catalog_action )
    refresh_catalog_action ( )
    var guidance : Label = host . _label ( CatalogGuidanceScript . explanation ( host , controls . get ( "entry" , { } ) , int ( controls [ "amount" ] . value ) if controls . get ( "amount" ) != null else 1 , str ( controls [ "kind" ] ) ) , 21 , "edc77a" )
    guidance . name = "CatalogDetailsExplanation"
    guidance . visible = not guidance . text . is_empty ( )
    modal_body . add_child ( guidance )
    if str ( controls [ "kind" ] ) == "build" :
        var effect : String = CatalogGuidanceScript . building_effect ( host , controls . get ( "entry" , { } ) )
        if not effect . is_empty ( ) :
            modal_body . add_child ( host . _label ( effect , 23 , "bad4c3" ) )
    var paragraphs : VBoxContainer = VBoxContainer . new ( )
    paragraphs . name = "CatalogDetailsParagraphs"
    paragraphs . add_theme_constant_override ( "separation" , 24 )
    modal_body . add_child ( paragraphs )
    var feature : Dictionary = controls . get ( "entry" , { } ) . get ( "planet_trait" , { } )
    if not feature . is_empty ( ) :
        host . planetary_ui . add_trait ( paragraphs , feature )
    for text : String in CatalogDetailsScript . paragraphs ( host , controls , host . detailed_descriptions , false , true ) :
        paragraphs . add_child ( ResourceInfo . label ( host , text , 23 ) )

    var requirements : Array = controls . get ( "entry" , { } ) . get ( "requirements" , [ ] )
    if not requirements . is_empty ( ) :
        paragraphs . add_child ( host . _label ( I18n . t ( "Wymagania" ) , 25 ) )
        var seen : Dictionary = { }
        for requirement : Dictionary in requirements :
            var group : String = str ( requirement . get ( "group" , "buildings" ) )
            var key : String = str ( requirement . get ( "key" , "" ) )
            var identity : String = group + ":" + key
            if seen . has ( identity ) :
                continue
            seen [ identity ] = true
            var current : int = int ( requirement . get ( "current" , host . state . get ( group , { } ) . get ( key , 0 ) ) )
            var caption : String = ( "✓ " if bool ( requirement . get ( "met" , false ) ) else "○ " ) + host . _server_text ( requirement . get ( "name" , key ) ) + " · %d/%d" % [ current , int ( requirement . get ( "level" , 0 ) ) ]
            var link : Button = host . _button ( caption , _open_catalog_target . bind ( group , key ) )
            link . name = "Requirement_" + key
            paragraphs . add_child ( link )


func refresh_catalog_action ( ) -> void :
    if not details_open ( ) or open_catalog_controls . is_empty ( ) or not is_instance_valid ( open_catalog_action ) or host . planned_queue_ui == null :
        return
    var amount : int = int ( open_catalog_controls [ "amount" ] . value ) if open_catalog_controls . get ( "amount" ) != null else 1
    host . planned_queue_ui . refresh_action_button ( open_catalog_action , open_catalog_controls . get ( "entry" , { } ) , str ( open_catalog_controls [ "kind" ] ) , amount )


func _open_catalog_target ( group : String , key : String ) -> void :

    if group == "research" and host . research_tree != null and host . research_tree . entries . has ( key ) :
        host . research_tree . open_details ( key )
        return
    if group == "megastructures" :
        host . megastructure_ui . open_projects ( )
        return
    var rows : Dictionary = { }
    if group == "buildings" :
        rows = host . building_rows
    elif group == "ships" :
        rows = host . ship_rows
    elif group == "defenses" :
        rows = host . defense_rows
    elif group == "research" :
        rows = host . research_rows
    if rows . has ( key ) :
        _open_catalog ( rows [ key ] )


func _catalog_signature ( controls : Dictionary ) -> String :

    var amount : int = int ( controls [ "amount" ] . value ) if controls . get ( "amount" ) != null else 1
    return JSON . stringify ( [ controls . get ( "entry" , { } ) , host . detailed_descriptions , amount , host . state . get ( "resources" , { } ) , host . state . get ( "production" , { } ) , host . state . get ( "production_status" , { } ) , host . state . get ( "limits" , { } ) , host . state . get ( "storage" , { } ) ] )


func refresh_description_mode ( ) -> void :
    if details_open ( ) and not open_catalog_controls . is_empty ( ) :
        if not is_instance_valid ( open_catalog_controls . get ( "panel" ) ) :
            close_details ( )
            return
        var scroll_y : int = modal_scroll . scroll_vertical
        _open_catalog ( open_catalog_controls )
        _restore_details_scroll ( scroll_y )


func update_wallet ( amount : int , enabled : bool ) -> void :


    header_wallet_title . text = I18n . t ( "Koło umiejętności" )
    header_wallet_amount . text = host . _number ( float ( amount ) )
    host . skill_wallet_button . visible = enabled
    host . skill_wallet_button . tooltip_text = I18n . t ( "Kryształy Roju · %s    Koło umiejętności ›" ) % host . _number ( float ( amount ) )
    header_wallet_crystal . texture = host . ArtLibrary . texture ( "swarm/crystal" ) if enabled else null
    _queue_fit_header ( )
    host . skill_entry . hide ( )


func refresh ( ) -> void :
    if details_open ( ) and not open_catalog_controls . is_empty ( ) :
        if not is_instance_valid ( open_catalog_controls . get ( "panel" ) ) :
            close_details ( )
        elif open_catalog_signature != _catalog_signature ( open_catalog_controls ) :
            var scroll_y : int = modal_scroll . scroll_vertical
            _open_catalog ( open_catalog_controls )
            _restore_details_scroll ( scroll_y )
    host . race_identity . hide ( )
    host . biome_toggle . hide ( )
    host . colony_panorama . show ( )
    race_button . icon = host . race_portrait . texture
    race_button . tooltip_text = str ( host . race_name . text )
    race_button . visible = race_button . icon != null
    host . skill_entry . hide ( )
    _compact_fleet ( )
    sync_navigation ( )


func _tap_row ( parent : Node , title : String , subtitle : String , texture : Texture2D , callback : Callable ) -> Button :
    var button : Button = host . _button ( "" , callback )
    button . custom_minimum_size . y = 108
    button . name = "CompactEntry"
    parent . add_child ( button )
    var margin : MarginContainer = MarginContainer . new ( )
    margin . mouse_filter = Control . MOUSE_FILTER_IGNORE
    margin . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    for side : String in [ "left" , "right" , "top" , "bottom" ] :
        margin . add_theme_constant_override ( "margin_" + side , 10 )
    button . add_child ( margin )
    var row : HBoxContainer = HBoxContainer . new ( )
    row . mouse_filter = Control . MOUSE_FILTER_IGNORE
    row . add_theme_constant_override ( "separation" , 12 )
    margin . add_child ( row )
    var art : TextureRect = TextureRect . new ( )
    art . texture = texture
    art . custom_minimum_size = Vector2 ( 82 , 70 )
    art . expand_mode = TextureRect . EXPAND_IGNORE_SIZE
    art . stretch_mode = TextureRect . STRETCH_KEEP_ASPECT_CENTERED
    art . mouse_filter = Control . MOUSE_FILTER_IGNORE
    row . add_child ( art )
    var info : VBoxContainer = VBoxContainer . new ( )
    info . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    info . mouse_filter = Control . MOUSE_FILTER_IGNORE
    row . add_child ( info )
    var heading : Label = host . _label ( title , 23 )
    heading . max_lines_visible = 2
    heading . text_overrun_behavior = TextServer . OVERRUN_TRIM_ELLIPSIS
    info . add_child ( heading )
    var sub : Label = host . _label ( subtitle , 19 , "a0b3a4" )
    sub . add_theme_font_size_override ( "font_size" , 19 )
    sub . max_lines_visible = 2
    sub . text_overrun_behavior = TextServer . OVERRUN_TRIM_ELLIPSIS
    info . add_child ( sub )
    button . set_meta ( "title_label" , heading )
    button . set_meta ( "subtitle_label" , sub )
    var arrow : Label = host . _label ( "›" , 28 )
    arrow . size_flags_horizontal = Control . SIZE_SHRINK_END
    row . add_child ( arrow )
    return button


func refresh_reports ( ) -> void :
    host . _refresh_report_scope ( )
    host . _update_unread_reports ( )
    var reports : Array = host . state . get ( "reports" , [ ] )
    var signature : String = JSON . stringify ( reports )
    if signature == host . reports_signature :
        return
    host . reports_signature = signature
    host . _clear ( host . report_list )
    if reports . is_empty ( ) :
        host . report_list . add_child ( host . _label ( I18n . t ( "Brak raportów. Wyślij zwiad, aby poznać sąsiednie planety." ) , 22 ) )
    for report : Dictionary in reports :
        var texture : Texture2D = ReportSummary.icon_texture(report)
        var row : Button = _tap_row ( host . report_list , host . _server_text ( report . get ( "title" , I18n . t ( "Raport" ) ) ) , host . _date ( float ( report . get ( "at" , 0 ) ) ) , texture , _open_report . bind ( report . duplicate ( true ) ) )
        row . name = "ReportEntry"
        row.set_meta("report_kind", ReportSummary.icon_kind(report))

        var heading : Label = row . get_meta ( "title_label" )
        var date : Label = row . get_meta ( "subtitle_label" )
        heading . custom_minimum_size . y = 29
        date . custom_minimum_size . y = 24
        for label : Label in [ heading , date ] :
            label . autowrap_mode = TextServer . AUTOWRAP_OFF
            label . clip_text = true
        heading . get_parent ( ) . alignment = BoxContainer . ALIGNMENT_CENTER


func _open_report ( report : Dictionary ) -> void :
    if host . beginner_guide != null :
        host . beginner_guide . mark_report_opened ( report )
    _begin_details ( host . _server_text ( report . get ( "title" , I18n . t ( "Raport" ) ) ) )
    modal_body . add_child ( host . _label ( host . _date ( float ( report . get ( "at" , 0 ) ) ) , 21 ) )
    ReportSummary . add_to ( host , modal_body , report )
    if bool ( report . get ( "battle_replay_available" , false ) ) :
        battle_viewer = BattleReplayScript . new ( )
        modal_body . add_child ( battle_viewer )
        battle_viewer . setup ( host , report )
    modal_body . add_child ( ResourceInfo . label ( host , ReportResourceText . text ( host , report ) , 23 ) )
    if int ( report . get ( "swarm_crystals" , 0 ) ) > 0 :
        modal_body . add_child ( host . _label ( I18n . t ( "Kryształy Roju · %d" ) % int ( report [ "swarm_crystals" ] ) , 23 ) )
    if report . has ( "planet_scout" ) :
        if report . has ( "scout" ) :
            host . planetary_ui . add_environment ( modal_body , report [ "planet_scout" ] . get ( "environment" , { } ) )
        else :
            host . planetary_ui . add_scout ( modal_body , report [ "planet_scout" ] )
    if report . has ( "scout" ) and report [ "scout" ] is Dictionary :
        host . _add_scout_summary ( modal_body , report [ "scout" ] )
        host . _add_scout_data ( modal_body , report [ "scout" ] )


func refresh_planets ( ) -> void :
    var active : Dictionary = { }
    for system : Dictionary in host . state . get ( "galaxy" , [ ] ) :
        if str ( system . get ( "id" , "" ) ) == host . selected_system :
            active = system
    var protection_status : Array = [ ]
    for planet : Dictionary in active . get ( "planets" , [ ] ) :
        protection_status . append ( float ( planet . get ( "protected_until" , 0 ) ) > host . _server_now ( ) )
    var signature : String = JSON . stringify ( active ) + str ( host . selected_planet ) + str ( host . state . get ( "player" , { } ) . get ( "id" , "" ) ) + str ( protection_status )
    if signature == host . system_signature :
        return
    host . system_signature = signature
    host . _clear ( host . planet_list )
    host . planet_actions . clear ( )
    host . system_heading . text = str ( active . get ( "name" , I18n . t ( "Wybierz układ" ) ) )
    host . system_coordinates . text = I18n . t ( "Sektor %s:%s · znane planety: %d" ) % [ host . _stat_number ( float ( active . get ( "x" , 0 ) ) ) , host . _stat_number ( float ( active . get ( "y" , 0 ) ) ) , active . get ( "planets" , [ ] ) . size ( ) ]
    var visibility : String = host . planetary_ui . visibility_text ( active )
    if not visibility . is_empty ( ) :
        host . planet_list . add_child ( host . _label ( visibility , 22 , "edc77a" ) )
    host . planetary_ui . galaxy_guidance . add_system_action ( host . planet_list , active )
    for planet : Dictionary in active . get ( "planets" , [ ] ) :
        var id : String = str ( planet . get ( "id" , "" ) )
        var owner : String = str ( planet . get ( "owner_type" , "empty" ) )
        var caption : String = I18n . t ( "○ Wolna planeta" )
        if owner != "empty" :
            caption = str ( planet . get ( "owner_name" , "" ) )
        if str ( planet . get ( "owner_id" , "" ) ) == str ( host . state . get ( "player" , { } ) . get ( "id" , "" ) ) :
            caption = I18n . t ( "● Twoja kolonia" )
        caption = host . planetary_ui . caption ( planet )
        var texture : Texture2D = host . ArtLibrary . planet_texture ( id )
        var row : Button = _tap_row ( host . planet_list , str ( planet . get ( "name" , I18n . t ( "Planeta" ) ) ) , caption , texture , _open_planet . bind ( id ) )


        if float ( planet . get ( "protected_until" , 0 ) ) > host . _server_now ( ) :
            var protected_label : Label = host . _label ( I18n . t ( "Chroniona" ) , 18 , "91c89b" )
            protected_label . name = "PlanetProtectedBadge"
            protected_label . autowrap_mode = TextServer . AUTOWRAP_OFF
            protected_label . size_flags_horizontal = Control . SIZE_SHRINK_END
            protected_label . size_flags_vertical = Control . SIZE_SHRINK_BEGIN
            var content_row : HBoxContainer = row . get_child ( 0 ) . get_child ( 0 )
            content_row . add_child ( protected_label )
            content_row . move_child ( protected_label , content_row . get_child_count ( ) - 2 )
        var title_label : Label = row . get_meta ( "title_label" )
        var subtitle_label : Label = row . get_meta ( "subtitle_label" )
        title_label . autowrap_mode = TextServer . AUTOWRAP_OFF
        title_label . max_lines_visible = 1
        subtitle_label . autowrap_mode = TextServer . AUTOWRAP_OFF
        var content : MarginContainer = row . get_child ( 0 )
        content . minimum_size_changed . connect ( func ( ) -> void :
            row . custom_minimum_size . y = maxf ( 108.0 , content . get_combined_minimum_size ( ) . y ) )
        row . custom_minimum_size . y = maxf ( 108.0 , content . get_combined_minimum_size ( ) . y )
        if str ( planet . get ( "environment" , { } ) . get ( "trait" , { } ) . get ( "status" , "" ) ) == "rare" :
            subtitle_label . add_theme_color_override ( "font_color" , Color ( "edc77a" ) )


func _open_planet ( id : String ) -> void :
    var planet : Dictionary = { }
    for system : Dictionary in host . state . get ( "galaxy" , [ ] ) :
        for candidate : Dictionary in system . get ( "planets" , [ ] ) :
            if str ( candidate . get ( "id" , "" ) ) == id :
                planet = candidate
    if planet . is_empty ( ) :
        return
    _begin_details ( str ( planet . get ( "name" , I18n . t ( "Planeta" ) ) ) )
    host . planetary_ui . add_target_summary ( modal_body , planet )
    host . planetary_ui . add_target_actions ( modal_body , planet )
    _details_art ( host . ArtLibrary . colony_texture ( id ) )
    var owner : String = str ( planet . get ( "owner_type" , "empty" ) )
    var owned : bool = str ( planet . get ( "owner_id" , "" ) ) == str ( host . state . get ( "player" , { } ) . get ( "id" , "" ) )
    host . planetary_ui . add_planet_details ( modal_body , planet )
    if not str ( planet . get ( "alliance_tag" , "" ) ) . is_empty ( ) :
        modal_body . add_child ( host . _label ( "[%s] %s" % [ str ( planet [ "alliance_tag" ] ) , str ( planet . get ( "alliance_name" , "" ) ) ] , 23 , "edc77a" ) )
    if not str ( host . state . get ( "alliance" , { } ) . get ( "id" , "" ) ) . is_empty ( ) and not owned and owner != "empty" :
        modal_body . add_child ( host . _button ( I18n . t ( "Operacje sojuszu" ) , host . alliance_ui . open_target . bind ( planet . duplicate ( true ) ) ) )
    if owner == "player" and not owned :
        modal_body . add_child ( host . _button ( I18n . t ( "Napisz wiadomość" ) , host . communications . open_private . bind ( str ( planet . get ( "owner_id" , "" ) ) , str ( planet . get ( "owner_name" , "" ) ) ) ) )
    if owner == "alien" :
        host . _swarm_planet_details ( modal_body , planet )

func _fleet_target_name ( fleet : Dictionary ) -> String :
    if str ( fleet . get ( "scout_scope" , "" ) ) == "system" :
        for system : Dictionary in host . state . get ( "galaxy" , [ ] ) :
            if str ( system . get ( "id" , "" ) ) == str ( fleet . get ( "target_system_id" , "" ) ) :
                return str ( system . get ( "name" , system . get ( "id" , "" ) ) )
    return str ( fleet . get ( "target_name" , I18n . t ( "Cel" ) ) )


func refresh_fleets ( ) -> void :
    var fleets : Array = host . state . get ( "fleets" , [ ] )
    var signature : String = JSON . stringify ( fleets )
    if signature == host . fleets_signature :
        return
    host . fleets_signature = signature
    host . _clear ( host . fleet_list )
    host . fleet_countdowns . clear ( )
    if fleets . is_empty ( ) :
        host . fleet_list . add_child ( host . _label ( I18n . t ( "Wszystkie floty są w bazach." ) , 22 ) )
    for fleet : Dictionary in fleets :
        var mission : String = str ( fleet . get ( "mission" , "scout" ) )
        var index : int = host . MISSION_KEYS . find ( mission )
        var caption : String = I18n . t ( "Zwiad całego układu" ) if str ( fleet . get ( "scout_scope" , "" ) ) == "system" else I18n . t ( str ( host . MISSION_NAMES [ index ] ) ) if index >= 0 else mission
        if mission == "alliance_attack" : caption = I18n . t ( "Wspólny atak" )
        if mission == "alliance_defense" : caption = I18n . t ( "Wsparcie obrony" )
        if str ( fleet . get ( "status" , "" ) ) == "holding" : caption += " · " + I18n . t ( "Stacjonuje" )
        if str ( fleet . get ( "status" , "" ) ) == "exploring" : caption += " · " + I18n . t ( "Poszukiwania" )
        var returning : bool = str ( fleet . get ( "status" , "outbound" ) ) == "returning"
        if returning :
            caption += I18n . t ( " • POWRÓT" )
        if str ( fleet . get ( "route" , { } ) . get ( "travel_mode" , "" ) ) == "tunnel" :
            caption += " · " + I18n . t ( "Tunel" )
        var key : String = str ( fleet . get ( "art_key" , "" ) )
        var texture : Texture2D = host . ArtLibrary . texture ( key ) if not key . is_empty ( ) else host . _texture ( "fleet" )
        var row : Button = host . _button ( "" , _open_fleet_details . bind ( fleet . duplicate ( true ) ) )
        row . name = "FleetMissionEntry"
        row . custom_minimum_size . y = 200
        row . size_flags_horizontal = Control . SIZE_EXPAND_FILL
        row . tooltip_text = "%s: %s → %s" % [ caption , str ( fleet . get ( "origin_name" , I18n . t ( "Baza" ) ) ) , _fleet_target_name ( fleet ) ]
        host . fleet_list . add_child ( row )
        var timeline = FleetMissionTimelineScript . new ( )
        timeline . name = "FleetMissionTimeline"
        var display_fleet : Dictionary = fleet . duplicate ( true )
        display_fleet [ "target_name" ] = _fleet_target_name ( fleet )
        timeline . setup ( display_fleet , caption , texture , FleetMissionTimelineScript . marker_color ( display_fleet ) , host . _server_now , host . _duration )
        row . add_child ( timeline )
        timeline . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
        timeline . offset_left = 14
        timeline . offset_right = -14
        timeline . offset_top = 12
        timeline . offset_bottom = -12
        row . set_meta ( "fleet_timeline" , timeline )


func _open_fleet_details ( fleet : Dictionary ) -> void :
    var returning : bool = str ( fleet . get ( "status" , "outbound" ) ) == "returning"
    var origin : String = str ( fleet . get ( "origin_name" , I18n . t ( "Baza" ) ) )
    var target : String = _fleet_target_name ( fleet )
    _begin_details ( "%s → %s" % [ target if returning else origin , origin if returning else target ] )
    if str ( fleet . get ( "scout_scope" , "" ) ) == "system" :
        modal_body . add_child ( host . _label ( I18n . t ( "Zwiad całego układu" ) , 25 ) )
    var art_key : String = str ( fleet . get ( "art_key" , "" ) )
    if not art_key . is_empty ( ) :
        _details_art ( host . ArtLibrary . texture ( art_key ) )
    modal_body . add_child ( host . _label ( host . _ships_text ( fleet . get ( "ships" , { } ) , fleet . get ( "ship_names" , { } ) ) , 23 ) )
    modal_body . add_child ( host . _label ( host . _date ( float ( fleet . get ( "arrives_at" , 0 ) ) ) , 23 ) )
    if str(fleet.get("mission","")) == "expedition" and bool(fleet.get("can_recall",false)):
        modal_body.add_child(host._label(I18n.t("Zawrócenie kończy wyprawę bez znalezisk. Zużyte paliwo nie jest zwracane."),21))
        var recall: Button = host._button(I18n.t("Zawróć ekspedycję"),func() -> void:
            if host.request_pending or not host.uncertain_action.is_empty():
                return
            host._request("/api/action",{"type":"recall_expedition","planet_id":host.selected_planet,"fleet_id":fleet.id,"request_id":host._new_request_id()},"action")
            close_details())
        recall.name = "RecallExpedition"
        modal_body.add_child(recall)
    if int ( fleet . get ( "swarm_crystals" , 0 ) ) > 0 :
        modal_body . add_child ( host . _label ( I18n . t ( "%d kryształów Roju · w drodze do bazy" ) % int ( fleet [ "swarm_crystals" ] ) , 23 ) )
