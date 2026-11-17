/* Test-only observer for the packaged FrameViz WebKitGTK 4.1 window. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <unistd.h>

static void renderer_result(void *view, void *result, void *data)
{
    (void)data;
    void *(*finish)(void *, void *, void **) =
        dlsym(RTLD_NEXT, "webkit_web_view_evaluate_javascript_finish");
    char *(*as_string)(void *) = dlsym(RTLD_NEXT, "jsc_value_to_string");
    void (*unref)(void *) = dlsym(RTLD_NEXT, "g_object_unref");
    void (*free_string)(void *) = dlsym(RTLD_NEXT, "g_free");
    void (*free_error)(void *) = dlsym(RTLD_NEXT, "g_error_free");
    if (!finish || !as_string || !unref || !free_string || !free_error)
        return;
    void *error = NULL;
    void *value = finish(view, result, &error);
    if (!value) {
        fprintf(stderr, "[FrameViz QA] WebGL probe returned no result\n");
        if (error)
            free_error(error);
        return;
    }
    char *description = as_string(value);
    fprintf(stderr, "[FrameViz QA] WebGL %s\n", description ? description : "unavailable");
    free_string(description);
    unref(value);
}

static int inspect_renderer(void *view)
{
    void (*evaluate)(void *, const char *, long, const char *, const char *, void *,
                     void (*)(void *, void *, void *), void *) =
        dlsym(RTLD_NEXT, "webkit_web_view_evaluate_javascript");
    if (!evaluate)
        return 0;
    const char *script =
        "(() => {"
        "const canvas = document.querySelector('#container canvas');"
        "const gl = canvas?.getContext('webgl2') ?? canvas?.getContext('webgl');"
        "if (!gl) return 'no FrameViz canvas on this page';"
        "const ext = gl.getExtension('WEBGL_debug_renderer_info');"
        "return JSON.stringify({version: gl.getParameter(gl.VERSION),"
        "vendor: gl.getParameter(ext ? ext.UNMASKED_VENDOR_WEBGL : gl.VENDOR),"
        "renderer: gl.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER),"
        "unmasked: Boolean(ext)});"
        "})()";
    evaluate(view, script, -1, NULL, NULL, NULL, renderer_result, NULL);
    return 0;
}

static void load_changed(void *view, int event, void *data)
{
    (void)data;
    if (event != 3) /* WEBKIT_LOAD_FINISHED */
        return;
    void *(*ref)(void *) = dlsym(RTLD_NEXT, "g_object_ref");
    void (*unref)(void *) = dlsym(RTLD_NEXT, "g_object_unref");
    unsigned int (*timeout)(int, unsigned int, int (*)(void *), void *, void (*)(void *)) =
        dlsym(RTLD_NEXT, "g_timeout_add_full");
    if (ref && unref && timeout)
        timeout(0, 800, inspect_renderer, ref(view), unref);
}

void webkit_web_view_load_uri(void *view, const char *uri)
{
    void (*load_uri)(void *, const char *) = dlsym(RTLD_NEXT, "webkit_web_view_load_uri");
    void *(*get_context)(void *) = dlsym(RTLD_NEXT, "webkit_web_view_get_context");
    int (*get_sandbox_enabled)(void *) = dlsym(RTLD_NEXT, "webkit_web_context_get_sandbox_enabled");
    unsigned long (*connect_signal)(void *, const char *, void (*)(void *, int, void *),
                                    void *, void *, int) = dlsym(RTLD_NEXT, "g_signal_connect_data");
    if (!load_uri)
        return;
    if (get_context && get_sandbox_enabled)
        fprintf(stderr, "[FrameViz QA] GTK WebContext pid=%ld sandbox_enabled=%d\n",
                (long)getpid(), get_sandbox_enabled(get_context(view)));
    if (connect_signal)
        connect_signal(view, "load-changed", load_changed, NULL, NULL, 0);
    load_uri(view, uri);
}
