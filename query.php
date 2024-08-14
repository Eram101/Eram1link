<?php
//YOU MPESA API KEYS
$consumerKey = "Qk3tJeARhJZB1VAAQc8oTUhPgxi8ipXYpsDpRYhbqBvtYX38"; //Fill with your app Consumer Key
$consumerSecret = "EU6zoIBaWOykIRScpMEp0An8m6RQgyThl3AsgKFszUOm8TqDKiqu21CSJs9by3kl"; //Fill with your app Consumer Secret
//ACCESS TOKEN URL
$access_token_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials';
$headers = ['Authorization: Basic ' . base64_encode($consumerKey . ':' . $consumerSecret)];
$ch = curl_init($access_token_url);
curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, TRUE);
curl_setopt($ch, CURLOPT_HEADER, FALSE);
curl_setopt($ch, CURLOPT_USERPWD, $consumerKey . ':' . $consumerSecret);
$result = curl_exec($ch);
$result = json_decode($result);
$access_token = $result->access_token;
curl_close($ch);

// Get CheckoutRequestID from the POST data
$CheckoutRequestID = $_POST['CheckoutRequestID'];

// Transaction status API URL
$api_url = 'https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query';

// Shortcode (Paybill or Till Number)
$BusinessShortCode = '174379';

// Timestamp
$timestamp = date('YmdHis');

// Lipa na Mpesa Online Passkey
$LipaNaMpesaPasskey = 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919';

// Password
$password = base64_encode($BusinessShortCode . $LipaNaMpesaPasskey . $timestamp);

// Prepare the request data
$data = [
    'BusinessShortCode' => $BusinessShortCode,
    'Password' => $password,
    'Timestamp' => $timestamp,
    'CheckoutRequestID' => $CheckoutRequestID
];

// Send the request
$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $api_url);
curl_setopt($ch, CURLOPT_HTTPHEADER, ['Authorization: Bearer ' . $access_token, 'Content-Type: application/json']);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, TRUE);
curl_setopt($ch, CURLOPT_POST, TRUE);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
$response = curl_exec($ch);
curl_close($ch);

echo $response;
?>
