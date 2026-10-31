class_name BillingClient extends Node

signal connected
signal disconnected
signal connect_error ( response_code : int , debug_message : String )
signal query_product_details_response ( response : Dictionary )
signal query_purchases_response ( response : Dictionary )
signal on_purchase_updated ( response : Dictionary )
signal consume_purchase_response ( response : Dictionary )
signal acknowledge_purchase_response ( response : Dictionary )


enum BillingResponseCode {
    OK = 0 ,
    USER_CANCELED = 1 ,
    SERVICE_UNAVAILABLE = 2 ,
    BILLING_UNAVAILABLE = 3 ,
    ITEM_UNAVAILABLE = 4 ,
    DEVELOPER_ERROR = 5 ,
    ERROR = 6 ,
    ITEM_ALREADY_OWNED = 7 ,
    ITEM_NOT_OWNED = 8 ,
    NETWORK_ERROR = 12 ,
    SERVICE_DISCONNECTED = -1 ,
    FEATURE_NOT_SUPPORTED = -2 ,
    SERVICE_TIMEOUT = -3
}

enum ConnectionState {
    DISCONNECTED ,
    CONNECTING ,
    CONNECTED ,
    CLOSED
}

enum ProductType {
    INAPP ,
    SUBS
}

enum PurchaseState {
    UNSPECIFIED_STATE ,
    PURCHASED ,
    PENDING ,
}

enum ReplacementMode {

    UNKNOWN_REPLACEMENT_MODE = 0 ,


    WITH_TIME_PRORATION = 1 ,

    CHARGE_PRORATED_PRICE = 2 ,

    WITHOUT_PRORATION = 3 ,


    CHARGE_FULL_PRICE = 4 ,

    DEFERRED = 5 ,

    KEEP_EXISTING = 6
}

var _plugin_singleton : JNISingleton
var _plugin_name : String = "GodotGooglePlayBilling"


func _init ( ) -> void :
    if Engine . has_singleton ( _plugin_name ) :
        _plugin_singleton = Engine . get_singleton ( _plugin_name )
        _plugin_singleton . initPlugin ( )
        _connect_signals ( )
    elif OS . has_feature ( "template" ) :
        printerr ( _plugin_name , " singleton not found!" )

func _connect_signals ( ) -> void :
    _plugin_singleton . connect ( "connected" , connected . emit )
    _plugin_singleton . connect ( "disconnected" , disconnected . emit )
    _plugin_singleton . connect ( "connect_error" , connect_error . emit )
    _plugin_singleton . connect ( "query_product_details_response" , query_product_details_response . emit )
    _plugin_singleton . connect ( "query_purchases_response" , query_purchases_response . emit )
    _plugin_singleton . connect ( "on_purchase_updated" , on_purchase_updated . emit )
    _plugin_singleton . connect ( "consume_purchase_response" , consume_purchase_response . emit )
    _plugin_singleton . connect ( "acknowledge_purchase_response" , acknowledge_purchase_response . emit )

func start_connection ( ) -> void :
    if _plugin_singleton :
        _plugin_singleton . startConnection ( )

func end_connection ( ) -> void :
    if _plugin_singleton :
        _plugin_singleton . endConnection ( )

func is_ready ( ) -> bool :
    if _plugin_singleton :
        return _plugin_singleton . isReady ( )
    return false

func get_connection_state ( ) -> int :
    if _plugin_singleton :
        return _plugin_singleton . getConnectionState ( )
    return ConnectionState . DISCONNECTED

func query_product_details ( product_list : PackedStringArray , product_type : ProductType ) -> void :
    var product_type_str = "inapp"
    if product_type == ProductType . SUBS :
        product_type_str = "subs"

    if _plugin_singleton :
        _plugin_singleton . queryProductDetails ( product_list , product_type_str )

func query_purchases ( product_type : ProductType , include_suspended_subs : bool = false ) -> void :
    var product_type_str = "inapp"
    if product_type == ProductType . SUBS :
        product_type_str = "subs"

    if _plugin_singleton :
        _plugin_singleton . queryPurchases ( product_type_str , include_suspended_subs )

func purchase ( product_id : String , purchase_option_id : String = "" , offer_id : String = "" , is_offer_personalized : bool = false ) -> Dictionary :
    if _plugin_singleton :
        return _plugin_singleton . purchase ( product_id , purchase_option_id , offer_id , is_offer_personalized )
    return Dictionary ( )

func purchase_subscription ( product_id : String , base_plan_id : String , offer_id : String = "" , is_offer_personalized : bool = false ) -> Dictionary :
    if _plugin_singleton :
        return _plugin_singleton . purchaseSubscription ( product_id , base_plan_id , offer_id , is_offer_personalized )
    return Dictionary ( )

func update_subscription ( old_product_id : String , old_purchase_token : String , replacement_mode : ReplacementMode , new_product_id : String , base_plan_id : String , offer_id : String = "" , is_offer_personalized : bool = false ) -> Dictionary :
    if _plugin_singleton :
        return _plugin_singleton . updateSubscription ( old_product_id , old_purchase_token , replacement_mode , new_product_id , base_plan_id , offer_id , is_offer_personalized )
    return Dictionary ( )

func consume_purchase ( purchase_token : String ) :
    if _plugin_singleton :
        _plugin_singleton . consumePurchase ( purchase_token )

func acknowledge_purchase ( purchase_token : String ) :
    if _plugin_singleton :
        _plugin_singleton . acknowledgePurchase ( purchase_token )

func set_obfuscated_account_id ( account_id : String ) :
    if _plugin_singleton :
        _plugin_singleton . setObfuscatedAccountId ( account_id )

func set_obfuscated_profile_id ( profile_id : String ) :
    if _plugin_singleton :
        _plugin_singleton . setObfuscatedProfileId ( profile_id )

func open_subscriptions_page ( product_id : String = "" ) :
    if _plugin_singleton :
        _plugin_singleton . openSubscriptions ( product_id )
