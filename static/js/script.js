document.addEventListener("DOMContentLoaded", () => {

    console.log("Student Management System Loaded");

    const deletes =
        document.querySelectorAll(".delete-btn");

    deletes.forEach(btn => {

        btn.addEventListener("click", function(e){

            if(!confirm(
                "Delete this student?"
            )){
                e.preventDefault();
            }

        });

    });

});
