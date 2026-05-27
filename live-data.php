<?php
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');

$allowed = [
    'truth_seekers_user_stats' => '/truth_seekers_user_stats.json',
    'girl_personalities' => '/home/znc/bots/atrum/personalities.json'
];

$key = $_GET['file'] ?? '';

if (!isset($allowed[$key])) {
    http_response_code(400);
    echo json_encode([
        'error' => 'bad file request',
        'allowed' => array_keys($allowed)
    ]);
    exit;
}

$path = $allowed[$key];

if (!file_exists($path)) {
    http_response_code(404);
    echo json_encode([
        'error' => 'file not found',
        'path' => $path
    ]);
    exit;
}

$data = file_get_contents($path);

if ($data === false) {
    http_response_code(500);
    echo json_encode([
        'error' => 'could not read file',
        'path' => $path
    ]);
    exit;
}

echo $data;
