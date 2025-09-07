---
layout: default
title: "Roguelike Map Generation Reports"
---

<style>
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    line-height: 1.6;
    margin: 0;
    padding: 20px;
    background-color: #f5f5f5;
}
.site-header {
    text-align: center;
    margin-bottom: 30px;
    padding: 40px 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 10px;
}
.site-header h1 {
    margin: 0;
    font-size: 3em;
}
.site-header .subtitle {
    margin: 15px 0 0 0;
    font-size: 1.2em;
    opacity: 0.9;
}
.reports-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
    gap: 20px;
    margin-top: 30px;
}
.report-card {
    background: white;
    border-radius: 10px;
    padding: 20px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    transition: transform 0.2s, box-shadow 0.2s;
}
.report-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(0,0,0,0.15);
}
.report-card h3 {
    margin: 0 0 10px 0;
    color: #2c3e50;
}
.report-card .date {
    color: #7f8c8d;
    font-size: 0.9em;
    margin-bottom: 15px;
}
.report-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin: 15px 0;
}
.stat-item {
    text-align: center;
    padding: 10px;
    background: #f8f9fa;
    border-radius: 5px;
}
.stat-value {
    font-weight: bold;
    font-size: 1.2em;
    color: #2c3e50;
}
.stat-label {
    font-size: 0.8em;
    color: #7f8c8d;
}
.read-more {
    display: inline-block;
    margin-top: 15px;
    padding: 8px 16px;
    background: #667eea;
    color: white;
    text-decoration: none;
    border-radius: 5px;
    transition: background 0.3s;
}
.read-more:hover {
    background: #5a6fd8;
    text-decoration: none;
    color: white;
}
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: #7f8c8d;
}
.empty-state h2 {
    margin-bottom: 15px;
    color: #2c3e50;
}
</style>

<div class="site-header">
    <h1>🏰 Roguelike Map Reports</h1>
    <div class="subtitle">AI-Generated Dungeon Maps with Verification Scores</div>
</div>

{% if site.posts.size == 0 %}
<div class="empty-state">
    <h2>No reports yet!</h2>
    <p>Generate some roguelike maps and run the conversion script to see your reports here.</p>
</div>
{% else %}

## Latest Reports

<div class="reports-grid">
{% for post in site.posts %}
    <div class="report-card">
        <h3><a href="{{ post.url | relative_url }}" style="text-decoration: none; color: #2c3e50;">{{ post.title }}</a></h3>
        <div class="date">{{ post.date | date: "%B %d, %Y" }}</div>
        
        {% if post.total_maps or post.avg_score %}
        <div class="report-stats">
            {% if post.total_maps %}
            <div class="stat-item">
                <div class="stat-value">{{ post.total_maps }}</div>
                <div class="stat-label">Total Maps</div>
            </div>
            {% endif %}
            {% if post.avg_score %}
            <div class="stat-item">
                <div class="stat-value">{{ post.avg_score }}/10</div>
                <div class="stat-label">Avg Score</div>
            </div>
            {% endif %}
        </div>
        {% endif %}
        
        {% if post.generation_date %}
        <p style="margin: 10px 0; color: #7f8c8d; font-size: 0.9em;">
            Generated: {{ post.generation_date }}
        </p>
        {% endif %}
        
        <a href="{{ post.url | relative_url }}" class="read-more">View Report →</a>
    </div>
{% endfor %}
</div>

{% endif %}