package org.anemy.sunshine;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.text.InputType;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.TextView;

public class MainActivity extends Activity {
    static final String DEFAULT_URL = "https://study.anemy.org/";
    static final String PREFS = "sunshine";
    static final String KEY_URL = "server_url";
    WebView web;
    TextView title;

    @SuppressLint("SetJavaScriptEnabled")
    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(R.layout.activity_main);
        title = findViewById(R.id.title);
        web = findViewById(R.id.web);
        title.setOnLongClickListener(v -> { askServer(); return true; });
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        // Android WebView 的 speechSynthesis 需要媒体自动播放权限，否则朗读被静音拦截
        s.setMediaPlaybackRequiresUserGesture(false);
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                return false;
            }
            @Override public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                if (r.isForMainFrame()) askServer();
            }
        });
        if (b == null) web.loadUrl(serverUrl());
        else web.restoreState(b);
    }

    String serverUrl() {
        String u = getSharedPreferences(PREFS, MODE_PRIVATE).getString(KEY_URL, DEFAULT_URL);
        if (u == null || u.trim().isEmpty()) return DEFAULT_URL;
        u = u.trim();
        if (!u.startsWith("http://") && !u.startsWith("https://")) u = "https://" + u;
        if (!u.endsWith("/")) u += "/";
        return u;
    }

    void askServer() {
        final EditText input = new EditText(this);
        input.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        input.setText(serverUrl());
        new AlertDialog.Builder(this)
            .setTitle("服务器地址")
            .setMessage("默认是官网。家里自建时再改，例如 http://192.168.1.8:9000/")
            .setView(input)
            .setPositiveButton("打开", (d, w) -> {
                String u = input.getText().toString().trim();
                if (u.isEmpty()) u = DEFAULT_URL;
                SharedPreferences.Editor ed = getSharedPreferences(PREFS, MODE_PRIVATE).edit();
                ed.putString(KEY_URL, u);
                ed.apply();
                web.loadUrl(serverUrl());
            })
            .setNegativeButton("取消", null)
            .show();
    }

    @Override protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }
}
