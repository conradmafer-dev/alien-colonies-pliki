extends RefCounted



var host
var panel : PanelContainer
var category_label : Label
var title_label : Label
var message_label : Label
var _request : HTTPRequest
var _last_url : String = ""
var _last_fetch : int = 0
var _generation : int = 0


func setup ( owner , parent : VBoxContainer ) -> void :
    host = owner
    panel = PanelContainer . new ( )
    panel . name = "LiveLoginAnnouncement"
    panel . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    panel . visible = false
    panel . add_theme_stylebox_override ( "panel" , host . _style ( "061827f0" , "4cc6eca5" , 20 , 23 ) )
    parent . add_child ( panel )
    var body : VBoxContainer = VBoxContainer . new ( )
    body . add_theme_constant_override ( "separation" , 10 )
    panel . add_child ( body )
    category_label = Label . new ( )
    category_label . name = "AnnouncementCategory"
    category_label . text = ""
    category_label . add_theme_font_size_override ( "font_size" , 17 )
    category_label . add_theme_color_override ( "font_color" , Color ( "61ddf3" ) )
    category_label . mouse_filter = Control . MOUSE_FILTER_IGNORE
    body . add_child ( category_label )
    title_label = Label . new ( )
    title_label . name = "AnnouncementHeading"
    title_label . add_theme_font_size_override ( "font_size" , 28 )
    title_label . add_theme_color_override ( "font_color" , Color ( "e9f6ff" ) )
    title_label . autowrap_mode = TextServer . AUTOWRAP_WORD_SMART
    title_label . mouse_filter = Control . MOUSE_FILTER_IGNORE
    body . add_child ( title_label )
    message_label = Label . new ( )
    message_label . name = "AnnouncementMessage"
    message_label . add_theme_font_size_override ( "font_size" , 20 )
    message_label . add_theme_color_override ( "font_color" , Color ( "c6dfea" ) )
    message_label . autowrap_mode = TextServer . AUTOWRAP_WORD_SMART
    message_label . mouse_filter = Control . MOUSE_FILTER_IGNORE
    body . add_child ( message_label )


func load_from_server ( force : bool = false ) -> void :
    if host == null or not is_instance_valid ( panel ) or not host . showing_login or host . _login_name_stage_active ( ) :
        return
    var url : String = str ( host . server_url ) . strip_edges ( ) . trim_suffix ( "/" )
    if not url . begins_with ( "https://" ) and not url . begins_with ( "http://127.0.0.1" ) :
        panel . visible = false
        return
    var now : int = Time . get_ticks_msec ( )
    if is_instance_valid ( _request ) :
        return
    if not force and url == _last_url and now - _last_fetch < 300000 :
        return
    _last_fetch = now
    _last_url = url
    _generation += 1
    var generation : int = _generation
    _request = HTTPRequest . new ( )
    _request . timeout = 9.0
    _request . max_redirects = 0
    host . add_child ( _request )
    _request . request_completed . connect ( _on_response . bind ( generation ) )
    var headers : PackedStringArray = PackedStringArray ( [ "Accept: application/json" , "Accept-Language: " + I18n . locale ] )
    if _request . request ( url + "/api/public/announcement" , headers , HTTPClient . METHOD_GET ) != OK :
        panel . visible = false
        _request . queue_free ( )
        _request = null


func _on_response ( result : int , status : int , _headers : PackedStringArray , bytes : PackedByteArray , generation : int ) -> void :
    if is_instance_valid ( _request ) :
        _request . queue_free ( )
    _request = null
    if generation != _generation or not is_instance_valid ( panel ) :
        return
    panel . visible = false
    if result != HTTPRequest . RESULT_SUCCESS or status != 200 :
        return
    var response : Variant = JSON . parse_string ( bytes . get_string_from_utf8 ( ) )
    if not response is Dictionary or not bool ( response . get ( "visible" , false ) ) or not response . get ( "announcement" ) is Dictionary :
        return
    var announcement : Dictionary = response [ "announcement" ]
    var heading : String = str ( announcement . get ( "title" , "" ) ) . strip_edges ( ) . substr ( 0 , 100 )
    var content : String = str ( announcement . get ( "body" , "" ) ) . strip_edges ( ) . substr ( 0 , 1600 )
    if heading . is_empty ( ) or content . is_empty ( ) :
        return
    var category : String = str ( announcement . get ( "category" , "news" ) )
    var names : Dictionary = { "news" : "AKTUALNOŚĆ" , "event" : "WYDARZENIE" , "update" : "AKTUALIZACJA" , "maintenance" : "PRZERWA TECHNICZNA" }
    category_label . text = I18n . t ( str ( names . get ( category , "AKTUALNOŚĆ" ) ) )
    title_label . text = heading
    message_label . text = content
    panel . visible = host . showing_login and not host . _login_name_stage_active ( )
    host . _update_login_art_layout . call_deferred ( )


func hide ( ) -> void :
    if is_instance_valid ( panel ) :
        panel . visible = false
        if host != null :
            host . _update_login_art_layout . call_deferred ( )


func invalidate ( ) -> void :
    _generation += 1
    _last_fetch = 0
    if is_instance_valid ( _request ) :
        _request . cancel_request ( )
        _request . queue_free ( )
    _request = null
    hide ( )
