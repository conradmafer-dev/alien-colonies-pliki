extends HBoxContainer




signal value_changed ( new_value : float )

const MAX_EXACT_INTEGER : float = 9007199254740990.0
const QuantityEditGate = preload ( "res://client/scripts/quantity_edit_gate.gd" )

var _minimum : float = 0.0
var _maximum : float = 100.0
var _step : float = 1.0
var _value : float = 0.0

var min_value : float :
    get :
        return _minimum
    set ( next ) :
        if not is_finite ( next ) :
            return
        _minimum = ceilf ( clampf ( next , - MAX_EXACT_INTEGER , MAX_EXACT_INTEGER ) )
        _maximum = maxf ( _maximum , _minimum )
        _set_value ( _value )

var max_value : float :
    get :
        return _maximum
    set ( next ) :
        if not is_finite ( next ) :
            return
        _maximum = floorf ( clampf ( next , - MAX_EXACT_INTEGER , MAX_EXACT_INTEGER ) )
        _minimum = minf ( _minimum , _maximum )
        _set_value ( _value )

var step : float :
    get :
        return _step
    set ( next ) :
        _step = maxf ( 1.0 , roundf ( absf ( next ) ) ) if is_finite ( next ) else 1.0

var value : float :
    get :
        return _value
    set ( next ) :
        _set_value ( next )

var minus_button : Button
var plus_button : Button
var editor : LineEdit
var edit_gate : Button


func _init ( ) -> void :
    mouse_filter = Control . MOUSE_FILTER_PASS


    size_flags_horizontal = Control . SIZE_SHRINK_BEGIN
    # Do not grow to the height of a neighbouring multiline ship description.
    size_flags_vertical = Control . SIZE_SHRINK_CENTER
    add_theme_constant_override ( "separation" , 8 )
    minus_button = _make_button ( "−" , I18n . t ( "Zmniejsz ilość" ) )
    add_child ( minus_button )
    editor = LineEdit . new ( )
    editor . name = "Quantity"
    editor . custom_minimum_size = Vector2 ( 88 , 76 )
    editor . size_flags_horizontal = Control . SIZE_EXPAND_FILL
    editor . alignment = HORIZONTAL_ALIGNMENT_CENTER
    editor . virtual_keyboard_type = LineEdit . KEYBOARD_TYPE_NUMBER
    editor . select_all_on_focus = true
    editor . mouse_filter = Control . MOUSE_FILTER_IGNORE
    editor . max_length = 18
    editor . tooltip_text = I18n . t ( "Wpisz ilość" )
    editor . add_theme_constant_override ( "minimum_character_width" , 3 )
    editor . add_theme_font_size_override ( "font_size" , 24 )
    add_child ( editor )
    edit_gate = QuantityEditGate . new ( )
    edit_gate . name = "TapToEdit"
    editor . add_child ( edit_gate )
    edit_gate . set_anchors_and_offsets_preset ( Control . PRESET_FULL_RECT )
    edit_gate . edit_requested . connect ( _begin_edit )
    plus_button = _make_button ( "+" , I18n . t ( "Zwiększ ilość" ) )
    add_child ( plus_button )
    minus_button . pressed . connect ( _change_by . bind ( -1.0 ) )
    plus_button . pressed . connect ( _change_by . bind ( 1.0 ) )
    editor . text_submitted . connect ( func ( _text : String ) -> void : apply ( ) )
    editor . focus_exited . connect ( apply )
    editor . resized . connect ( _fit_editor_font )
    _refresh_display ( true )


func _ready ( ) -> void :
    I18n . language_changed . connect ( _refresh_language )


    for kind : String in [ "normal" , "focus" ] :
        var style : StyleBox = editor . get_theme_stylebox ( kind ) . duplicate ( ) as StyleBox
        style . content_margin_left = 6
        style . content_margin_right = 6
        editor . add_theme_stylebox_override ( kind , style )
    _fit_editor_font ( )


func _make_button ( caption : String , hint : String ) -> Button :
    var button : Button = Button . new ( )
    button . text = caption
    button . tooltip_text = hint
    button . custom_minimum_size = Vector2 ( 72 , 76 )
    button . mouse_filter = Control . MOUSE_FILTER_PASS
    button . action_mode = BaseButton . ACTION_MODE_BUTTON_RELEASE
    button . add_theme_font_size_override ( "font_size" , 30 )
    return button


func get_line_edit ( ) -> LineEdit :
    return editor


func _begin_edit ( ) -> void :
    if not editor . editable or not is_visible_in_tree ( ) :
        return


    editor . edit ( )
    editor . select_all ( )


func apply ( ) -> void :
    _set_value ( _edited_value ( ) , true )


func _edited_value ( ) -> float :
    var text_value : String = editor . text . strip_edges ( )
    if not text_value . is_valid_int ( ) :
        return _value
    var parsed : float = text_value . to_float ( )
    return parsed if is_finite ( parsed ) else _value


func _change_by ( direction : float ) -> void :

    var base : float = clampf ( _edited_value ( ) , _minimum , _maximum )
    _set_value ( base + direction * _step , true )


func _set_value ( next : float , force_text : bool = false ) -> void :
    if not is_finite ( next ) :
        _refresh_display ( force_text )
        return
    var clamped : float = roundf ( clampf ( next , _minimum , _maximum ) )
    var changed : bool = clamped != _value
    _value = clamped
    _refresh_display ( force_text or changed )
    if changed :
        value_changed . emit ( _value )


func _refresh_display ( force_text : bool = false ) -> void :
    if not is_instance_valid ( editor ) :
        return
    if force_text or not editor . has_focus ( ) :
        editor . text = str ( int ( _value ) )
    minus_button . disabled = _value <= _minimum
    plus_button . disabled = _value >= _maximum
    _fit_editor_font ( )


func _fit_editor_font ( ) -> void :
    if not is_instance_valid ( editor ) :
        return
    var font : Font = editor . get_theme_font ( "font" )
    var style : StyleBox = editor . get_theme_stylebox ( "normal" )
    var available : float = maxf ( editor . size . x , editor . custom_minimum_size . x ) - style . get_minimum_size ( ) . x - 8.0
    var font_size : int = 24
    while font_size > 18 and font . get_string_size ( editor . text , HORIZONTAL_ALIGNMENT_LEFT , -1 , font_size ) . x > available :
        font_size -= 1
    editor . add_theme_font_size_override ( "font_size" , font_size )


func _refresh_language ( ) -> void :

    minus_button . tooltip_text = I18n . t ( "Zmniejsz ilość" )
    plus_button . tooltip_text = I18n . t ( "Zwiększ ilość" )
    editor . tooltip_text = I18n . t ( "Wpisz ilość" )
