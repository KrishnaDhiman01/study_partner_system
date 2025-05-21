console.log("Study Partner System Main JS Loaded.");
function autoCloseFlashMessages() {
    const flashMessages = document.querySelectorAll('.flash-messages-container .alert');
    flashMessages.forEach(function(alertBox) {
        setTimeout(() => {
             if (alertBox.style.display !== 'none') { 
                 alertBox.style.transition = 'opacity 0.5s ease';
                 alertBox.style.opacity = '0';
                 setTimeout(() => {
                     if (alertBox.parentElement) { 
                        alertBox.style.display = 'none';
                     }
                 }, 500); 
             }
        }, 5000);
    });
}


document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM fully loaded and parsed");
    
    autoCloseFlashMessages();
});