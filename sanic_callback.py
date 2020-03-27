from sanic import Sanic
from sanic.response import json

app = Sanic()


@app.post("/callback")
async def post_handler(request):
    print(request)
    print(request.body)
    return json({})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
