// eslint-disable-next-line import/unambiguous
'use strict';

window.addEventListener("DOMContentLoaded", () => 
{
    // eslint-disable-next-line no-undef
    const button_array = document.querySelectorAll(".btn");
    const output_children = document.querySelector(".debat-detail-output").children;

    function display_block(element) {
        // Hide all children first
        Array.from(output_children).forEach(child => {
            child.style.display = "none";
        });
        
        // Show the selected element
        element.style.display = "block";
    }
    
    // The forEach loop iterates over each button in the button_array
    // First parameter is the button, second is the index
    button_array.forEach((button, i) => {
        button.addEventListener("click", () => {
            display_block(output_children[i]);
        });
    });
    
});
