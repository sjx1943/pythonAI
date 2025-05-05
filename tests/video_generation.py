import gradio as gr
import time
from zhipuai import ZhipuAI
import requests

client = ZhipuAI(api_key='f91c87d6b19446c3a5f7452e99dd1c3f.rFUZxLlrv5Cq2p68') # api_key 配置成你自己的key


def cogvideo_inference(prompt):
    print(prompt)
    response = client.videos.generations(model="cogvideo", prompt=prompt)
    task_id = response.id
    response = client.videos.retrieve_videos_result(id=task_id)
    print(response)
    task_status = response.task_status
    get_cnt = 0
    result_response = response
    while task_status == 'PROCESSING' and get_cnt <= 40:
        result_response = client.videos.retrieve_videos_result(id=task_id)
        print(result_response)
        task_status = result_response.task_status
        if task_status == 'SUCCESS':
            break
        time.sleep(30)
        get_cnt += 1

    if result_response.video_result is not None:
        url = result_response.video_result[0].url
        file_name = url.split('/')[-1]
        res = requests.get(url, stream=True)
        with open(file_name, 'wb') as f1:
            for chunk in res.iter_content(chunk_size=102400):
                f1.write(chunk)
        return file_name
    else:
        return None


def main():
    with gr.Blocks() as demo:
        with gr.Row():
            with gr.Column():
                gr.HTML(
                    """
                    <h1 style='text-align: center'>
                   CogVideoX 文生视频Demo
                    </h1>
                    """
                )
                gr.HTML(
                    """
                    <h3 style='text-align: center'>

                    智谱AI token注册申请！
                    <a href='https://bigmodel.cn/' target='_blank'>智谱开放平台</a>
                    </h3>
                    """
                )

        with gr.Row():
            with gr.Column():
                prompt_text = gr.Textbox(
                    show_label=False,
                    placeholder="Enter prompt text here",
                    lines=4)
                submit_button = gr.Button("Run Inference")

            with gr.Column():
                output_video = gr.Video()

        submit_button.click(
            fn=cogvideo_inference,
            inputs=[prompt_text],
            outputs=output_video
        )
        gr.Examples(
            examples=[
                [" (推镜头+黄昏的柔和光线)+一个孤独的旅人(身着风衣，手持行李箱)+缓缓走向远方的火车站+一个空旷的火车站台(落日的余晖洒满整个站台，铁轨延伸到视线的尽头)+(一种离别与期待的交织氛围)"],
                ["(特写镜头+明亮清晰的光线)+一个高清的人类指头(细节清晰可见)+一只迷你斑马在指头上缓慢行走+人类手指的局部特写(指纹和皮肤纹理清晰，小斑马如蚂蚁般大小在其上行走)+(一种新奇而有趣的氛围)"],
                ["(拉镜头+晨光熹微)+一位晨跑的跑者(身着运动装备，精神饱满)+在公园小径上稳步前行+清晨的公园(鸟语花香，晨光透过树叶洒落)+(一种活力与健康并存的氛围)"],
                ["(旋转镜头+黄昏的暖色调光线)+一对恋人(相依相偎在海边)+静静地欣赏着落日余晖+海边的沙滩(海浪轻拍岸边，夕阳渐渐下沉)+(一种浪漫与宁静交融的氛围)"],
                ["(特写镜头+明亮的室内光线)+一杯冒着热气的咖啡(旁边摆放着一本翻开的书)+咖啡杯中热气升腾，散发出诱人香气+安静的咖啡馆角落(窗外是繁忙的街道，窗内是静谧的阅读空间)+(一种悠闲与专注并存的氛围)"],
                ["(移镜头+蓝天白云下的自然光线)+一群孩子在草地上玩耍(欢笑声此起彼伏)+追逐嬉戏，快乐无比+开阔的绿草地(远处有小山和树林作为背景)+(一种欢乐与自由的氛围)"],
                ["(推镜头+雨后的清新空气与微光)+一朵沾满雨滴的玫瑰(花瓣更加鲜艳，绿叶更加翠绿)+在微风中轻轻摇曳+雨后的花园(四周是湿润的土壤和翠绿的植物)+(一种清新与生机盎然的氛围)"],
            ],
            fn=cogvideo_inference,
            inputs=[prompt_text],
            outputs=[output_video],
            cache_examples=False,
        )

    demo.launch(debug=True)


if __name__ == "__main__":
    main()