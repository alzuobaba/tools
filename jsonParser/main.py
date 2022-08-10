# encoding: utf-8
import json
import re


# 删除“//”标志后的注释
def rmCmt(instr):
    qtCnt = cmtPos = slashPos = 0
    rearLine = instr
    # rearline: 前一个comment_flag之后的字符串，
    # 双引号里的comment_flag不是注释标志，所以遇到这种情况，仍需继续查找后续的comment_flag
    comment_flags = ["//", "#"]
    for comment_flag in comment_flags:
        while rearLine.find(comment_flag) >= 0:  # 查找comment_flag
            slashPos = rearLine.find(comment_flag)
            cmtPos += slashPos
            # print 'slashPos: ' + str(slashPos)
            headLine = rearLine[:slashPos]
            while headLine.find('"') >= 0:  # 查找comment_flag前的双引号
                qtPos = headLine.find('"')
                if not isEscapeOpr(headLine[:qtPos]):  # 如果双引号没有被转义
                    qtCnt += 1  # 双引号的数量加1
                headLine = headLine[qtPos + 1:]
            if qtCnt % 2 == 0:  # 如果双引号的数量为偶数，则说明comment_flag是注释标志
                return instr[:cmtPos]
            rearLine = rearLine[slashPos + len(comment_flag):]
            # print rearLine
            cmtPos += len(comment_flag)
    return instr


# 判断是否为转义字符
def isEscapeOpr(instr):
    if len(instr) <= 0:
        return False
    cnt = 0
    while instr[-1] == '\\':
        cnt += 1
        instr = instr[:-1]
    if cnt % 2 == 1:
        return True
    else:
        return False


# 从json文件的路径JsonPath读取该文件，返回json对象
def loadJson(JsonPath):
    try:
        srcJson = open(JsonPath, 'r', encoding='utf-8')
    except:
        print('cannot open ' + JsonPath)
        quit()
    dstJsonStr = ''
    for line in srcJson.readlines():
        if not re.match(r'\s*//', line) and not re.match(r'\s*\n', line):
            dstJsonStr += rmCmt(line)
        else:
            print('fdf')
    # print dstJsonStr
    # printRes(dstJsonStr)
    dstJson = {}
    try:
        dstJson = json.loads(dstJsonStr)
        return dstJson
    except:
        print(JsonPath + ' is not a valid json file')
        quit()


# 带缩进地在屏幕输出json字符串
def printRes(resStr):
    resStr = resStr.replace(',', ',\n')
    resStr = resStr.replace('{', '{\n')
    resStr = resStr.replace(':{', ':\n{')
    resStr = resStr.replace('}', '\n}')
    resStr = resStr.replace('[', '\n[\n')
    resStr = resStr.replace(']', '\n]')
    resStr = resStr
    resArray = resStr.split('\n')
    preBlank = ''
    for line in resArray:
        if len(line) == 0:
            continue
        lastChar = line[len(line) - 1]
        lastTwoChars = line[len(line) - 2:]
        if lastChar in {'}', ']'} or lastTwoChars in {'},', '],'}:
            preBlank = preBlank[:len(preBlank) - 2]
        try:
            print(preBlank + line)
        except:
            print(preBlank + '[%This line cannot be decoded%]')
        if lastChar == '{' or lastChar == '[':
            preBlank += ' ' * 2


if __name__ == '__main__':
    m = loadJson('Box.json')
    print(m)
