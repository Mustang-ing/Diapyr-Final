import $ from "jquery";

import render_debate_form from "../../templates/diapyr/formulaire_debat.hbs";

// Mount the debate form into its wrapper
export function mount_debate_form(): void {
    const $wrapper = $("#diapyr-debate-form-wrapper");
    if ($wrapper.length === 0) {
        return; // container not present
    }
    // Only inject once unless you need re-render
    if ($wrapper.children().length === 0) {
        $wrapper.html(render_debate_form({}));
        attach_handlers();
    }
}

function show_section(): void {
    $("#diapyr-debate-form-section").removeClass("notdisplayed");
    $("#diapyr-debate-form-launch").addClass("notdisplayed");
}
function hide_section(): void {
    $("#diapyr-debate-form-section").addClass("notdisplayed");
    $("#diapyr-debate-form-launch").removeClass("notdisplayed");
}

function attach_handlers(): void {
    $(document).on("click", "#diapyr-show-form", () => {
        show_section();
        mount_debate_form();
    });
    $(document).on("click", "#diapyr-toggle-form", () => {
        hide_section();
    });

    $(document).on("submit", "#diapyr-debate-create-form", (e) => {
        e.preventDefault();
        void (async () => {
            const $form = $(e.currentTarget);
            const data: Record<string, string> = {};
            for (const field of $form.serializeArray()) {
                data[field.name] = field.value.trim();
            }
            const payload = {
                title: data.diapyr_debate_name,
                description: data.diapyr_debate_description,
                subscription_minutes: data.diapyr_subscription_delay,
                max_per_group: data.diapyr_max_per_group,
                time_between_round: data.diapyr_phase_duration,
            };
            if (!payload.title || !payload.subscription_minutes || !payload.max_per_group || !payload.time_between_round) {
                show_message("error", $("#diapyr-debate-form-messages"), "Champs requis manquants.");
                return;
            }
            try {
                const tokenVal = $("input[name='csrfmiddlewaretoken']").val();
                const csrftoken = typeof tokenVal === "string" ? tokenVal : undefined;
                const headers: Record<string, string> = {"Content-Type": "application/json"};
                if (csrftoken) {
                    headers["X-CSRFToken"] = csrftoken;
                }
                const resp = await fetch("/json/diapyr/debates/create", {
                    method: "POST",
                    headers,
                    body: JSON.stringify(payload),
                    credentials: "same-origin",
                });  
                if (resp.ok) {
                    show_message("success", $("#diapyr-debate-form-messages"), "Débat créé.");
                    $form.trigger("reset");
                } else {
                    const text = await resp.text();
                    const trimmed = text.slice(0, 200) || "Erreur serveur.";
                    show_message("error", $("#diapyr-debate-form-messages"), trimmed);
                }
            } catch (error) {
                const msg = error instanceof Error ? error.message : "Erreur inattendue.";
                show_message("error", $("#diapyr-debate-form-messages"), msg);
            }
        })();
    });
}

function show_message(type: "success" | "error", $container: JQuery, msg: string): void {
    const cls = type === "success" ? "alert alert-success" : "alert alert-error";
    $container
        .attr("class", cls)
        .text(msg)
        .attr("role", "alert");
}

// Auto-init once DOM is ready (ui_init.js runs late, but we ensure early mount as well)
$(() => {
    mount_debate_form();
    $(document).on("click", "#alt_create_debat", (ev) => {
        ev.preventDefault();
        show_section();
        mount_debate_form();
        const section = document.querySelector("#diapyr-debate-form-section");
        section?.scrollIntoView({behavior: "smooth", block: "start"});
    });
});

// Expose helper for navbar button to trigger the embedded form
declare global {
    // Declare as global function property to avoid Window interface merging lint complaint
    // eslint-disable-next-line no-var
    var showDiapyrDebateForm: (() => void) | undefined;
}

window.showDiapyrDebateForm = () => {
    show_section();
    mount_debate_form();
    const section = document.querySelector("#diapyr-debate-form-section");
    if (section) {
        section.scrollIntoView({behavior: "smooth", block: "start"});
    }
};
