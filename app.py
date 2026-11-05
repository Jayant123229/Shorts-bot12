from flask import Flask, request, jsonify
import os, json, asyncio, urllib.parse, requests
import google.generativeai as genai
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from PIL import Image, ImageDraw

app = Flask(__name__)

@app.route('/generate-video', methods=['POST'])
def generate_video():
    try:
        data = request.json
        ep_num = data.get("episode_number", 1)
        series_title = data.get("series_title", "Raat Ka Rahasya")
        char_dna = data.get("character_dna", "A young Indian man named Kabir")
        story_so_far = data.get("story_so_far", "Kabir ko ek mysterious call aaya hai.")
        last_cliffhanger = data.get("last_cliffhanger", "Darwaza kholo.")
        gemini_api_key = data.get("gemini_api_key")

        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
        Write Episode {ep_num} of thriller series '{series_title}' featuring Kabir.
        Story so far: {story_so_far}
        Previous cliffhanger: {last_cliffhanger}

        Give 5 short scenes in Hindi (Devanagari script) with English visual descriptions. End on a new cliffhanger.

        Return ONLY valid JSON in this format:
        {{
          "episode_title": "Title in Hinglish",
          "youtube_description": "2 line description + hashtags",
          "scenes": [
            {{
              "narration_hindi": "Hindi voiceover line",
              "scene_visual_english": "Visual description mentioning Kabir"
            }}
          ],
          "updated_story_summary": "Summary",
          "new_cliffhanger": "Cliffhanger"
        }}
        """

        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        ep_data = json.loads(clean_text)

        clips = []

        async def make_audio(text, filename):
            communicate = edge_tts.Communicate(text, "hi-IN-MadhurNeural", rate="+5%")
            await communicate.save(filename)

        for i, scene in enumerate(ep_data["scenes"]):
            audio_path = f"scene_{i}.mp3"
            img_path = f"scene_{i}.jpg"
            
            asyncio.run(make_audio(scene["narration_hindi"], audio_path))
            
            full_img_prompt = f"{char_dna}, {scene['scene_visual_english']}, vertical 9:16 wallpaper, high quality"
            encoded_prompt = urllib.parse.quote(full_img_prompt)
            img_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=720&height=1280&seed=42&nologo=true"
            
            try:
                img_res = requests.get(img_url, timeout=60)
                if img_res.status_code == 200 and len(img_res.content) > 1000:
                    with open(img_path, "wb") as f:
                        f.write(img_res.content)
                else:
                    raise Exception("Bad image")
            except:
                img = Image.new('RGB', (720, 1280), color = (20, 20, 20))
                d = ImageDraw.Draw(img)
                d.text((50, 600), f"Scene {i+1}", fill=(255, 255, 255))
                img.save(img_path)
                
            audio_clip = AudioFileClip(audio_path)
            img_clip = ImageClip(img_path).set_duration(audio_clip.duration)
            img_clip = img_clip.set_audio(audio_clip)
            clips.append(img_clip)

        final_video = concatenate_videoclips(clips, method="compose")
        output_filename = "final_episode.mp4"
        final_video.write_videofile(output_filename, fps=24, codec="libx264", audio_codec="aac")

        return jsonify({
            "status": "success",
            "title": f"{ep_data['episode_title']} | Ep {ep_num} - {series_title} #shorts",
            "description": f"{ep_data['youtube_description']}\n\n#shorts",
            "video_url": output_filename, # Make.com ke liye
            "updated_summary": ep_data["updated_story_summary"],
            "new_cliffhanger": ep_data["new_cliffhanger"]
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
