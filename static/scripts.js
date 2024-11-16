
$(document).ready(function () {

    // CSRF Token setup - Fetch and store securely
    let csrfToken = null;

    function getCsrfToken() {
        return $.ajax({ // Return the AJAX promise
            url: '/csrf-token',
            type: 'GET',
            dataType: 'json',
            // Note: Synchronous XHR is deprecated due to performance reasons.
            //  Keeping it synchronous here to avoid complexity, but refactor to async if possible.
            async: false 
        });

    }



    // Enhanced handleFormSubmission function
    function handleFormSubmission(formId, successCallback, additionalData = {}) {
        $(formId).submit(function (e) {
            e.preventDefault();

            // Get a fresh CSRF token for each request (important for security)
            getCsrfToken()
                .done(function(data) { // Use .done() to handle the asynchronous response
                    csrfToken = data.csrf_token;

                    $.ajax({
                        url: $(this).attr('action'),
                        type: 'POST',
                        data: $.extend($(this).serialize(), additionalData), // Include additional data if needed
                        dataType: 'json',
                        headers: { 'X-CSRFToken': csrfToken },
                        success: function (data) {
                            if (data.success) {
                                successCallback(data); // Pass the response data to the callback
                            } else {
                                displayFormError(formId, data.error || "An error occurred.");
                            }
                        },
                        error: function (error) {
                            console.error("Form submission failed:", error);
                            displayFormError(formId, "An unexpected error occurred. Please try again.");
                        }
                        // Note: removed 'complete' callback as we're now getting a fresh CSRF token before each request

                    });

                }).fail(function() {
                     displayFormError(formId, "Could not obtain CSRF token"); // Error getting token

                });
        });
    }





    // Function to display form errors
    function displayFormError(formId, message) {
        const errorElement = $(formId + " .error-message");
        if (errorElement.length) { // Check if error element exists
            errorElement.text(message).show();
        } else {
            console.error("Error element not found for form: ", formId);
            alert(message); // Fallback if element is missing
        }

    }




    // Login form submission
    handleFormSubmission("#loginForm", function (data) {
        $('#loginModal').modal('hide');

        // Redirect based on server response (recommended for security)
        if (data.redirect_url) {
            window.location.href = data.redirect_url;
        } else {
            location.reload();
        }
    });




    // Signup form submission
    handleFormSubmission("#signupForm", function (data) {
        $('#signupModal').modal('hide');


        if (data.redirect_url) {
            window.location.href = data.redirect_url;
        } else {

            location.reload();
        }
    });

});

 function callGeminiAPI(fileId, feature) {
    const apiUrl = `/gemini_api/${fileId}/${feature}`;
    // 1. Fetch the file content (choose one of the methods below)
    
    // Method 1: If content is on the page (replace with your editor's API if needed)
    // const textContent = $(`#file-content-${fileId}`).val();  // For a textarea or input field
    // const textContent = tinymce.get(`editor-${fileId}`).getContent(); // Example for TinyMCE editor

    // Method 2: Fetch content with AJAX (if not readily available on page)
    function fetchFileContent(fileId, callback) { // Helper function to fetch content
      $.ajax({
          url: `/get_file_content/${fileId}`,
          type: 'GET',
          dataType: 'json', // Expect JSON response
          success: callback,
          error: function(error) {
              displayAPIError("Error fetching file content."); // Show specific error message
          }
      });
    }


    fetchFileContent(fileId, function(data) {
       const textContent = data.content; // Access content from the AJAX response
      
        // 2. Proceed with Gemini API call after fetching content
        $.ajax({
          url: apiUrl,
          type: 'POST',
          contentType: 'application/json',
          dataType: 'json',
          headers: { 'X-CSRFToken': csrfToken },
          data: JSON.stringify({ type: feature, text_content: textContent }),
          success: function(response) {
              // 3. Securely handle the API response (example using a template)
              displayAPIResult(response);
          },
          error: function(error) {
              let errorMessage = "Gemini API call failed.";
              if (error.responseJSON && error.responseJSON.error) {
                  errorMessage = error.responseJSON.error;
              } else if (error.status === 404) {
                  errorMessage = "API endpoint not found.";
              }  // ... other specific error cases
              displayAPIError(errorMessage);
          }
        });

    });





    // 4. Helper functions for display (prevent XSS)
    function displayAPIResult(response) {
      // Sanitize the HTML content if it's not already handled in your templating engine
        const sanitizedHTML = DOMPurify.sanitize(JSON.stringify(response, null, 2)); // Sanitize HTML content
        $("#api-results").html(sanitizedHTML);

    }



    function displayAPIError(errorMessage) {
        $("#api-results").html(`<div class="alert alert-danger">${DOMPurify.sanitize(errorMessage)}</div>`);
    }


}

    let socket = io(); // Initialize Socket.IO connection
$(window).on('beforeunload', function() { // Emit 'leave' before page unload
    if (currentFileId) {
        socket.emit('leave', { file_id: currentFileId });
    }
});


    // Drag and Drop
    let dropArea = $('#file-drop-area');
    ;['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.on(eventName, preventDefaults, false);
    })


    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }


    ;['dragenter', 'dragover'].forEach(eventName => {
        dropArea.on(eventName, highlight, false)
    });

    ;['dragleave', 'drop'].forEach(eventName => {
        dropArea.on(eventName, unHighlight, false)
    });




    function highlight(e) {
        dropArea.addClass('highlight');
    }


    function unHighlight(e) {
        dropArea.removeClass('highlight');
    }



    dropArea.on('drop', handleDrop, false);



    function handleDrop(e) {
        let dt = e.originalEvent.dataTransfer
        let files = dt.files



        handleFiles(files);
    }



    function handleFiles(files) {
        ([...files]).forEach(uploadFile)

    }




    function uploadFile(file) {

        let formData = new FormData()

        formData.append('file', file);
        formData.append('csrf_token', csrfToken);

        $.ajax({
            url: "{{ url_for('upload') }}", // Flask upload route
            type: 'POST',
            data: formData,

            contentType: false,
            processData: false,
            xhr: function () {  // Handle upload progress if you want to show progress bar
                let myXhr = $.ajaxSettings.xhr();


                return myXhr;
            },
            success: function (response) {

                displayFilesAndFolders(); // Refresh file list

            },
error: function (error) {
    console.error(`Gemini API call failed for ${feature}:`, error);
    let errorMessage = "An error occurred.";
    if (error.responseJSON && error.responseJSON.error) {
        errorMessage = error.responseJSON.error; // Use server-provided error message
    } else if (error.status == 404) {
      errorMessage = "Resource not found.";
    } // ... other error cases ...

    $('#api-results').html(`<div class="alert alert-danger">${errorMessage}</div>`); // Display error to user

}

        });


    }

    // Sorting
    $('.sort-btn').click(function () {
        const sortBy = $(this).data('sort-by');


        $.ajax({
            url: '/files_and_folders',  // Your Flask route to get updated data
            type: 'GET',
            data: { 'sort_by': sortBy }, // Add sort parameter to the URL
            success: function (data) {

                displayFilesAndFolders(); // Update the display with sorted data

            },
            error: function(error) {
              // ... handle errors ...
            }

        });



    });


    // Gemini API button handling (enhanced)
    $(document).on('click', '.gemini-api-btn', function() {  // Use delegated event handling
        const fileId = $(this).data('file-id');
        const feature = $(this).data('feature');
        callGeminiAPI(fileId, feature);
    });


    // Socket.IO for real-time collaboration
    let currentFileId = null;  // Store the ID of the file being edited

    $(document).on('click', '.edit-btn', function () {   // Delegated event handling
        const fileId = $(this).data('file-id');

        currentFileId = fileId;
        socket.emit('join', { file_id: fileId });
    });


    // ... (Handle leaving the room when closing editor or navigating away)

    $('#file-content').on('input', function () { // Replace #file-content with your editor's selector

        if (currentFileId) {

            let content = $(this).val();

            socket.emit('edit', { file_id: currentFileId, content: content });
        }
    });




    socket.on('update', function (data) {

        if (currentFileId == data.file_id) {
            $('#file-content').val(data.content);  // Update the editor content
        }



    });

});