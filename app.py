from flask import Flask, render_template
import folium

app = Flask(__name__)

@app.route('/')
def home():
    # Create a simple folium map centered at Chennai
    m = folium.Map(location=[13.0827, 80.2707], zoom_start=6)
    folium.Marker([13.0827, 80.2707], tooltip="Chennai").add_to(m)
    m.save('templates/map.html')
    return render_template('map.html')

if __name__ == '__main__':
    app.run(debug=True)
