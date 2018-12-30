import pylab,random

def flipPlot(minExp,maxExp):
    ratios = []
    diffs = []
    xAxis = []

    for exp in range(minExp,maxExp+1):
        xAxis.append(2**exp)
    for numFlips in xAxis:
        numHeads = 0
        for n in range(numFlips):
            if random.random() < 0.5:
                numHeads += 1
        numTails = numFlips - 1
        ratios.append(numHeads / float(numTails))
        diffs.append(abs(numHeads-numTails))

    pylab.title('difference between heads and tails')

    pylab.xlabel('Number of Flips')

    pylab.ylabel('abs(#Heads - #Tails)')

    pylab.plot(xAxis, diffs)
    pylab.figure()

    pylab.title('Heads/Tails ratio')

    pylab.xlabel('Number of Flips')
    pylab.ylabel('#Heads / #Tails ratio')

    pylab.plot(xAxis, ratios)

random.seed(0)
flipPlot(4,20)