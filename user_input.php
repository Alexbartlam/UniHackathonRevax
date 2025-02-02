<?php
// Set the environment variable for the Mistral API key
putenv("MISTRAL_API_KEY=your_api_key_here");

// Get the user input from the POST request
$user_input = $_POST['user_input'];

// Sanitize input to avoid any security issues (optional but recommended)
$user_input = escapeshellarg($user_input);

// Debug: Log the received user input
error_log("User Input: " . $user_input);

// Execute Search.py with the user input and capture the output
$search_output = shell_exec("python3 /var/www/html/Case_bank/Search.py " . escapeshellarg($user_input));

// Return the result as plain text (you can return it as JSON if you prefer)
echo $search_output;

// Debug: Log the output of Search.py
if ($search_output === null) {
    error_log("Error executing Search.py.");
} else {
    error_log("Search Output: " . $search_output);
}

// Combine the search result with the original user input
$combined_input = $user_input . " " . $search_output;

// Execute Mistral_query.py with the combined input and capture the output
$mistral_output = shell_exec("python3 /var/www/html/mistral_query.py " . escapeshellarg($combined_input));

// Debug: Log the output of Mistral_query.py
if ($mistral_output === null) {
    error_log("Error executing Mistral_query.py.");
} else {
    error_log("Mistral Output: " . $mistral_output);
}

// Return the result as plain text (you can return it as JSON if you prefer)
echo $mistral_output;
?>
