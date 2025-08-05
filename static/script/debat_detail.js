// eslint-disable-next-line import/unambiguous
'use strict';


/* This script handles the dynamic display of debate details based on button clicks.
   It hides all sections initially and only displays the section corresponding to the clicked button.
    The buttons are expected to be in the class "btn" and the sections in the class
*/

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
