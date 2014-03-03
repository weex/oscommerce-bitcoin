<?php
/*

  $Id: ipn.php,v 0.4.1.0 beta 2007/02/18 07:08:00 Alex Li Exp $
  Copyright (c) 2007 AlexStudio

  osCommerce Bitcoin Payment Module
  bpn.php
  Copyright (c) 2012 David Sterry

  Released under the GNU General Public License

*/
chdir('../../../../'); // OSC catalog directory
require('includes/application_top.php');
require(DIR_WS_CLASSES . 'payment.php');

// Include language files for the email notifications
if (tep_not_null($_GET['language'])) {
    include(DIR_WS_LANGUAGES . $_GET['language'] . '/' . FILENAME_CHECKOUT_PROCESS);
    $language_query = tep_db_query("
        select languages_id
        from " . TABLE_LANGUAGES . "
        where directory = '" . $_GET['language'] . "'");
    $language_array = tep_db_fetch_array($language_query);
    $language_id = $language_array['languages_id'];
} else {
    if (isset($languages_id)) {
        $language_id = $languages_id;
        $language_query = tep_db_query("
            select directory
            from " . TABLE_LANGUAGES . "
            where languages_id = '" . $language_id . "'");
        $language_array = tep_db_fetch_array($language_query);
        $language_dir = $language_array['directory'];
        include(DIR_WS_LANGUAGES . $language_dir . '/' . FILENAME_CHECKOUT_PROCESS);
    } else {
        // Default to english language
        include(DIR_WS_LANGUAGES . 'english/' . FILENAME_CHECKOUT_PROCESS);
        $language_id = 1; // OSC default for english
    }
}

$parameters = array();
foreach ($_POST as $key => $value)
    $parameters[$key] = $value;

// Validate used notification key
$bpn_key_query = tep_db_query("
    select configuration_value
    from configuration
    where configuration_key = 'MODULE_PAYMENT_BITCOIN_NOTIFICATION_KEY'");
$bpn_key_array = tep_db_fetch_array($bpn_key_query);
$bpn_key = $bpn_key_array['configuration_value'];
if ($parameters['bpn_key'] == $bpn_key) {
    $result = 'Verified';
    $bpn_ok = true;
    $send_debug_email = false;
} else {
    $result = 'Invalid';
    $bpn_ok = false;
    $send_debug_email = true;
    $debug_reason = 'Invalid notification key: \''.$parameters['bpn_key'].'\'';
}

// Order ID should only have numbers
$order_num = preg_replace('/[^0-9]/','',$parameters['orders_id']);
if (!empty($order_num)) {
    $order_check = tep_db_query("
        select orders_id
        from " . TABLE_ORDERS_STATUS_HISTORY . "
        where orders_id = ". $order_num);
    $order_found = (tep_db_num_rows($order_check) > 0);
    if (!$order_found) {
        $send_debug_email = true;
        $debug_reason = 'order_id not found: \''.$order_num.'\'';
    }
} else {
    $order_found = 0;
    $send_debug_email = true;
    $debug_reason = 'Invalid order id: \''.$parameters['orders_id'].'\'';
}

if ($order_found && $bpn_ok) {
    $order_ok = tep_db_fetch_array($order_check);
    $order_id = tep_db_prepare_input($order_ok['orders_id']);
    $order_query = tep_db_query("
        select customers_id, customers_name, customers_email_address,
            date_purchased, orders_status, currency, currency_value
        from " . TABLE_ORDERS . "
        where orders_id = '" . (int)$order_id . "'");
    $order = tep_db_fetch_array($order_query);

    // Update the order status
    $total_query = tep_db_query("
        select value
        from " . TABLE_ORDERS_TOTAL . "
        where orders_id = '" . (int)$order_id . "'
            and class = 'ot_total' limit 1");
    $total = tep_db_fetch_array($total_query);
    $order_status_id = DEFAULT_ORDERS_STATUS_ID;
    $orders_statuses = array();
    $orders_status_array = array();
    $orders_status_query = tep_db_query("
        select orders_status_id, orders_status_name
        from " . TABLE_ORDERS_STATUS . "
        where language_id = '" . (int)$language_id . "'");
    while ($orders_status = tep_db_fetch_array($orders_status_query)) {
        $orders_statuses[] = array('id' => $orders_status['orders_status_id'],
                                'text' => $orders_status['orders_status_name']);
        $status_id = $orders_status['orders_status_id'];
        $status_name = $orders_status['orders_status_name'];
        $orders_status_array[$status_id] = $status_name;
    }

    $email = STORE_NAME . "\n" .
    EMAIL_SEPARATOR . "\n" .
    EMAIL_TEXT_ORDER_NUMBER . ' ' . $order_id . "\n" .
    EMAIL_TEXT_INVOICE_URL . ' ' .
        tep_href_link(FILENAME_ACCOUNT_HISTORY_INFO, 'order_id=' .
        $order_id, 'SSL', false, false) . "\n" .
    EMAIL_TEXT_DATE_ORDERED . ' ' .
        tep_date_long($order['date_purchased']) . "\n\n" .
        sprintf(EMAIL_TEXT_STATUS_UPDATE, $orders_status_array[$order_status_id]);
    tep_mail($order['customers_name'], $order['customers_email_address'],
        EMAIL_TEXT_SUBJECT, $email, STORE_OWNER, STORE_OWNER_EMAIL_ADDRESS);

    $customer_notified = '1';
    $order_status_id = 2; // 2 == Processing

    $sql_data_array = array('orders_id' => (int)$order_id,
                  'orders_status_id' => $order_status_id,
                  'date_added' => 'now()',
                  'customer_notified' => $customer_notified,
                  'comments' => "Bitcoin Txn " . $result . "\n" . $comment_status);
    tep_db_perform(TABLE_ORDERS_STATUS_HISTORY, $sql_data_array);
    tep_db_query("update " . TABLE_ORDERS .
        " set orders_status = '" . $order_status_id .
        "', last_modified = now() where orders_id = '" . (int)$order_id . "'");
}

// If something went wrong, send out debug email
if ($send_debug_email && trim(MODULE_PAYMENT_BITCOIN_DEBUG_EMAIL) != '' ) {
    $email_body = $debug_reason . "\n\n";

    $email_body .= '$_POST:' . "\n\n";
    foreach ($_POST as $key => $value)
        $email_body .= $key . '=' . $value . "\n";

    $email_body .= "\n" . '$_GET:' . "\n\n";
    foreach ($_GET as $key => $value)
        $email_body .= $key . '=' . $value . "\n";

    tep_mail(STORE_OWNER, MODULE_PAYMENT_BITCOIN_DEBUG_EMAIL,
        'osCommerce Bitcoin: Invalid Request to bpn.php', $email_body,
        STORE_OWNER, STORE_OWNER_EMAIL_ADDRESS);

    error_log('bpn.php: '.$debug_reason.'. Debug email sent.');
    http_response_code(500);
}

require('includes/application_bottom.php');
?>
