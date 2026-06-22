// ─────────────────────────────────────────────
// Student Management System JS
// ─────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {

    // Auto hide alerts after 5 seconds
    const alerts = document.querySelectorAll(".alert");

    alerts.forEach(alert => {
        setTimeout(() => {
            alert.classList.remove("show");
            alert.classList.add("fade");
        }, 5000);
    });

    // Confirm delete buttons
    const deleteButtons = document.querySelectorAll(".btn-danger");

    deleteButtons.forEach(btn => {
        btn.addEventListener("click", function (e) {

            const confirmDelete = confirm(
                "Are you sure you want to delete this record?"
            );

            if (!confirmDelete) {
                e.preventDefault();
            }

        });
    });

    // Search filter for tables
    const searchInput = document.getElementById("tableSearch");

    if (searchInput) {

        searchInput.addEventListener("keyup", function () {

            let filter = this.value.toLowerCase();

            let rows = document.querySelectorAll("tbody tr");

            rows.forEach(row => {

                let text = row.innerText.toLowerCase();

                row.style.display =
                    text.includes(filter)
                        ? ""
                        : "none";

            });

        });

    }

    // Smooth scroll
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {

        anchor.addEventListener("click", function (e) {

            e.preventDefault();

            document.querySelector(
                this.getAttribute("href")
            ).scrollIntoView({
                behavior: "smooth"
            });

        });

    });

});

// ─────────────────────────────────────────────
// Attendance Summary
// ─────────────────────────────────────────────

function attendanceStats() {

    let present =
        document.querySelectorAll(
            "select option[value='P']:checked"
        ).length;

    let absent =
        document.querySelectorAll(
            "select option[value='A']:checked"
        ).length;

    let leave =
        document.querySelectorAll(
            "select option[value='L']:checked"
        ).length;

    console.log("Present:", present);
    console.log("Absent:", absent);
    console.log("Leave:", leave);

}

// ─────────────────────────────────────────────
// Export Helper
// ─────────────────────────────────────────────

function exportMessage() {

    alert(
        "Student data export started."
    );

}

// ─────────────────────────────────────────────
// Dashboard Greeting
// ─────────────────────────────────────────────

function dashboardGreeting() {

    const hour = new Date().getHours();

    let msg = "Welcome";

    if (hour < 12) {

        msg = "Good Morning";

    } else if (hour < 18) {

        msg = "Good Afternoon";

    } else {

        msg = "Good Evening";

    }

    console.log(msg);

}

dashboardGreeting();
