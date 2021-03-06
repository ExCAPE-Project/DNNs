#Copyright (C) 2016-2019 Andreas Mayr, Guenter Klambauer, Thomas Unterthiner, Sepp Hochreiter
#Licensed under original BSD License (see LICENSE-ExCAPE at base directory) for members of the Horizon 2020 Project ExCAPE (Grant Agreement no. 671555)
#Licensed under GNU General Public License v3.0 (see LICENSE at base directory) for the general public

currentLR=hyperParams.iloc[paramNr].learningRate
currentDropout=hyperParams.iloc[paramNr].dropout
currentIDropout=hyperParams.iloc[paramNr].idropout
currentL1Penalty=hyperParams.iloc[paramNr].l1Penalty
currentL2Penalty=hyperParams.iloc[paramNr].l2Penalty
currentMom=hyperParams.iloc[paramNr].mom



reportTrainAUC=[]
reportTrainAP=[]
reportTestAUC=[]
reportTestAP=[]
sumTrainAUC=np.zeros(nrOutputTargets)
sumTrainAUC[:]=np.nan
sumTrainAP=np.zeros(nrOutputTargets)
sumTrainAP[:]=np.nan
sumTestAUC=np.zeros(nrOutputTargets)
sumTestAUC[:]=np.nan
sumTestAP=np.zeros(nrOutputTargets)
sumTestAP[:]=np.nan
startEpoch=0
minibatchCounterTrain=0
minibatchCounterTest=0
minibatchReportNr=0



exec(open(modelScript).read(), globals())
session.run(init)
session.run(biasInitOp, feed_dict={biasInit: trainBias.astype(np.float32)})
if (normalizeGlobalSparse or normalizeLocalSparse) and (nrSparseFeatures>0.5):
  session.run(sparseMeanInitOp, feed_dict={sparseMeanInit: trainSparseDiv2.reshape(1,-1)})
  session.run(sparseMeanWSparseOp.op)

session.run(scaleTrainId, feed_dict={ inputDropout: currentIDropout, hiddenDropout: currentDropout })
session.run(scaleTrainHd, feed_dict={ inputDropout: currentIDropout, hiddenDropout: currentDropout })



if continueComputations and loadScript!="":
  exec(open(loadScript).read(), globals())
endEpoch=nrEpochs



if nrSparseFeatures>0.5:
  session.run(sparseMeanWSparseOp.op)

if runEpochs:
  for epoch in range(startEpoch, endEpoch):
    print(epoch)
    
    if np.any(session.run(checkNA)):
      print("\n", file=dbgOutput)
      print("Attention: NaN detected! Computation stopped!\n", file=dbgOutput)
      saveFilename=savePrefix+".error"
      saveFile=open(saveFilename, "wb")
      errorNr=0
      pickle.dump(errorNr, saveFile)
      saveFile.close()
      break
    
    if not np.isnan(stopAtMinibatch):
      if minibatchReportNr>stopAtMinibatch:
        break
    
    if epoch%50==0:
      if saveComputations and saveScript!="":
        exec(open(saveScript).read(), globals())
    
    print("\n", file=dbgOutput)
    print("epoch: "+str(epoch)+"\n", file=dbgOutput)
    print("\n", file=dbgOutput)
    idxSamples=[arr[1] for arr in sklearn.model_selection.KFold(n_splits=int(math.ceil(len(trainSamples)/batchSize)), shuffle=True).split(np.arange(len(trainSamples)))]
    for i in range(len(idxSamples)):
      
      myfeedDict={
        inputDropout: currentIDropout,
        hiddenDropout: currentDropout,
        lrGeneral: currentLR,
        l2PenaltyWeight: currentL2Penalty,
        l2PenaltyBias: 0.0,
        l1PenaltyWeight: currentL1Penalty,
        l1PenaltyBias: 0.0,
        mom: currentMom,
        is_training: False
      }
      
      if nrDenseFeatures>0.5:
        batchDenseX=trainDenseInput[idxSamples[i]]
        myfeedDict.update({
          xDenseData: batchDenseX
        })
      
      if nrSparseFeatures>0.5:
        batchSparseX=trainSparseInput[idxSamples[i],:].copy()
        batchSparseX.sort_indices()
        nonzx=batchSparseX.nonzero()
        valnonzx=(batchSparseX)[nonzx[0],nonzx[1]]
        myfeedDict.update({
          xIndices: np.int64(np.vstack(nonzx).T), 
          xValues: valnonzx.A.flatten(), 
          xDim: [len(idxSamples[i]), batchSparseX.shape[1]]
        })
      
      if useDenseOutputNetTrain:
        batchDenseY=trainDenseOutput[idxSamples[i]]
        myfeedDict.update({
          yDenseData: batchDenseY
        })
        session.run(optimizerDense, feed_dict=myfeedDict)
      
      if not useDenseOutputNetTrain:
        batchSparseY=trainSparseOutput[idxSamples[i]].copy()
        batchSparseY.sort_indices()
        nonzy=batchSparseY.nonzero()
        valnonzy=(batchSparseY)[nonzy[0],nonzy[1]]
        myfeedDict.update({
          yIndices: np.int64(np.vstack(nonzy).T), 
          yValues: valnonzy.A.flatten(), 
          yDim: [len(idxSamples[i]), batchSparseY.shape[1]]
        })
        session.run(optimizerSparse, feed_dict=myfeedDict)
      
      if nrSparseFeatures>0.5:
        if normalizeGlobalSparse or normalizeLocalSparse:
          session.run(sparseMeanWSparseOp.op)
      
      
      
      session.run(scalePredictId, feed_dict={ inputDropout: currentIDropout, hiddenDropout: currentDropout })
      session.run(scalePredictHd, feed_dict={ inputDropout: currentIDropout, hiddenDropout: currentDropout })
      
      
      
      minibatchCounterTrain=minibatchCounterTrain+1
      if (minibatchCounterTrain==minibatchesPerReportTrain) and (not np.any(session.run(checkNA))):
        if computeTrainPredictions:
          predDenseTrain=[]
          if not (sparseOutputData is None):
            predSparseTrain=trainSparseOutput.copy().astype(np.float32)
            predSparseTrain.data[:]=-1
          idxSamplesEval=[arr[1] for arr in sklearn.model_selection.KFold(n_splits=int(math.ceil(len(trainSamples)/batchSize)), shuffle=False).split(np.arange(len(trainSamples)))]
          for j in range(len(idxSamplesEval)):
            
            myfeedDict={
              inputDropout: 0.0,
              hiddenDropout: 0.0,
              is_training: False
            }
            
            if nrDenseFeatures>0.5:
              batchDenseX=trainDenseInput[idxSamplesEval[j]]
              myfeedDict.update({
                xDenseData: batchDenseX
              })
            
            if nrSparseFeatures>0.5:
              batchSparseX=trainSparseInput[idxSamplesEval[j],:].copy()
              batchSparseX.sort_indices()
              nonzx=batchSparseX.nonzero()
              valnonzx=(batchSparseX)[nonzx[0],nonzx[1]]
              myfeedDict.update({
                xIndices: np.int64(np.vstack(nonzx).T), 
                xValues: valnonzx.A.flatten(), 
                xDim: [len(idxSamplesEval[j]), batchSparseX.shape[1]]
              })
            
            if useDenseOutputNetPred:
              if compPerformanceTrain:
                batchDenseY=trainDenseOutput[idxSamplesEval[j]]
              predDenseTrain.append(session.run(predNetwork, feed_dict=myfeedDict))
            
            if not useDenseOutputNetPred:
              if compPerformanceTrain:
                batchSparseY=trainSparseOutput[idxSamplesEval[j]].copy()
                batchSparseY.sort_indices()
                nonzy=batchSparseY.nonzero()
                valnonzy=(batchSparseY)[nonzy[0],nonzy[1]]
                myfeedDict.update({
                  yIndices: np.int64(np.vstack(nonzy).T)
                })
                predSparseTrain[min(idxSamplesEval[j])+nonzy[0],nonzy[1]]=session.run(predNetworkSparse, feed_dict=myfeedDict)
          
          if useDenseOutputNetPred:
            predDenseTrain=np.vstack(predDenseTrain)
            if compPerformanceTrain:
              sumTrainAUC=np.array(utilsLib.calculateAUCs(trainDenseOutput, predDenseTrain))
              sumTrainAP=np.array(utilsLib.calculateAPs(trainDenseOutput, predDenseTrain))
          
          if not useDenseOutputNetPred:
            if compPerformanceTrain:
              predSparseTrainTransposed=predSparseTrain.T.tocsr()
              predSparseTrain=None
              predSparseTrainTransposed.sort_indices()
              sumTrainAUC=np.array(utilsLib.calculateSparseAUCs(trainSparseOutputTransposed, predSparseTrainTransposed))
              sumTrainAP=np.array(utilsLib.calculateSparseAPs(trainSparseOutputTransposed, predSparseTrainTransposed))
              predSparseTrainTransposed=None
          
          if compPerformanceTrain:
            reportTrainAUC.append(sumTrainAUC)
            reportTrainAP.append(sumTrainAP)
            print("\n", file=dbgOutput)
            # print("Train AUC: ", file=dbgOutput)
            # print(sumTrainAUC[0:500], file=dbgOutput)
            # print("\n", file=dbgOutput)
            # print("Train AP: ", file=dbgOutput)
            # print(sumTrainAP[0:500], file=dbgOutput)
            # print("\n", file=dbgOutput)
            print("Train Mean AUC: ", file=dbgOutput)
            print(np.nanmean(sumTrainAUC), file=dbgOutput)
            print("\n", file=dbgOutput)
            # print("Train Mean AP: ", file=dbgOutput)
            # print(np.nanmean(sumTrainAP), file=dbgOutput)
            # print("\n", file=dbgOutput)
            dbgOutput.flush()
        
        
        
      if minibatchCounterTrain==minibatchesPerReportTrain:
        minibatchCounterTrain=0
      
      
      
      minibatchCounterTest=minibatchCounterTest+1
      if (minibatchCounterTest==minibatchesPerReportTest) and (not np.any(session.run(checkNA))):
        if computeTestPredictions:
          predDenseTest=[]
          if not (sparseOutputData is None):
            predSparseTest=testSparseOutput.copy().astype(np.float32)
            predSparseTest.data[:]=-1
          
          idxSamplesEval=[arr[1] for arr in sklearn.model_selection.KFold(n_splits=int(math.ceil(len(testSamples)/batchSize)), shuffle=False).split(np.arange(len(testSamples)))]
          for j in range(len(idxSamplesEval)):
            
            myfeedDict={
              inputDropout: 0.0,
              hiddenDropout: 0.0,
              is_training: False
            }
            
            if nrDenseFeatures>0.5:
              batchDenseX=testDenseInput[idxSamplesEval[j]]
              myfeedDict.update({
                xDenseData: batchDenseX
              })
            
            if nrSparseFeatures>0.5:
              batchSparseX=testSparseInput[idxSamplesEval[j],:].copy()
              batchSparseX.sort_indices()
              nonzx=batchSparseX.nonzero()
              valnonzx=(batchSparseX)[nonzx[0],nonzx[1]]
              myfeedDict.update({
                xIndices: np.int64(np.vstack(nonzx).T), 
                xValues: valnonzx.A.flatten(), 
                xDim: [len(idxSamplesEval[j]), batchSparseX.shape[1]]
              })
            
            if useDenseOutputNetPred:
              if compPerformanceTest:
                batchDenseY=testDenseOutput[idxSamplesEval[j]]
              predDenseTest.append(session.run(predNetwork, feed_dict=myfeedDict))
            
            if not useDenseOutputNetPred:
              if compPerformanceTest:
                batchSparseY=testSparseOutput[idxSamplesEval[j]].copy()
                batchSparseY.sort_indices()
                nonzy=batchSparseY.nonzero()
                valnonzy=(batchSparseY)[nonzy[0],nonzy[1]]
                myfeedDict.update({
                  yIndices: np.int64(np.vstack(nonzy).T)
                })
                predSparseTest[min(idxSamplesEval[j])+nonzy[0],nonzy[1]]=session.run(predNetworkSparse, feed_dict=myfeedDict)
          
          if useDenseOutputNetPred:
            predDenseTest=np.vstack(predDenseTest)
            if compPerformanceTest:
              sumTestAUC=np.array(utilsLib.calculateAUCs(testDenseOutput, predDenseTest))
              sumTestAP=np.array(utilsLib.calculateAPs(testDenseOutput, predDenseTest))
            if savePredictionsAtBestIter:
              predDenseBestIter[:, bestIterPerTask>=minibatchReportNr]=predDenseTest[:, bestIterPerTask>=minibatchReportNr]
          
          if not useDenseOutputNetPred:
            if savePredictionsAtBestIter:
              nonzp=predSparseTest.nonzero()
              useEntries=np.in1d(nonzp[1], np.where(bestIterPerTask>=minibatchReportNr)[0])
              if np.sum(useEntries)>0.5:
                nonzpFilter=(nonzp[0][useEntries], nonzp[1][useEntries])
                predSparseBestIter[nonzpFilter[0],nonzpFilter[1]]=predSparseTest[nonzpFilter[0],nonzpFilter[1]]
            if compPerformanceTest:
              predSparseTestTransposed=predSparseTest.copy().T.tocsr()
              predSparseTest=None
              predSparseTestTransposed.sort_indices()
              sumTestAUC=np.array(utilsLib.calculateSparseAUCs(testSparseOutputTransposed, predSparseTestTransposed))
              sumTestAP=np.array(utilsLib.calculateSparseAPs(testSparseOutputTransposed, predSparseTestTransposed))
              predSparseTestTransposed=None
          
          if logPerformanceAtBestIter:
            reportAUCBestIter[bestIterPerTask>=minibatchReportNr]=np.array(sumTestAUC)[bestIterPerTask>=minibatchReportNr]
            reportAPBestIter[bestIterPerTask>=minibatchReportNr]=np.array(sumTestAP)[bestIterPerTask>=minibatchReportNr]
          
          
          
          if compPerformanceTest:
            reportTestAUC.append(sumTestAUC)
            reportTestAP.append(sumTestAP)
            print("\n", file=dbgOutput)
            # print("Test AUC: ", file=dbgOutput)
            # print(sumTestAUC[0:500], file=dbgOutput)
            # print("\n", file=dbgOutput)
            # print("Test AP: ", file=dbgOutput)
            # print(sumTestAP[0:500], file=dbgOutput)
            # print("\n", file=dbgOutput)
            print("Test Mean AUC: ", file=dbgOutput)
            print(np.nanmean(sumTestAUC), file=dbgOutput)
            print("\n", file=dbgOutput)
            # print("Test Mean AP: ", file=dbgOutput)
            # print(np.nanmean(sumTestAP), file=dbgOutput)
            # print("\n", file=dbgOutput)
            dbgOutput.flush()
        
        
        
      if minibatchCounterTest==minibatchesPerReportTest:
        minibatchCounterTest=0
        minibatchReportNr=minibatchReportNr+1
      
      session.run(scaleTrainId, feed_dict={ inputDropout: currentIDropout, hiddenDropout: currentDropout })
      session.run(scaleTrainHd, feed_dict={ inputDropout: currentIDropout, hiddenDropout: currentDropout })
      
      
      
      if not np.isnan(stopAtMinibatch):
        if minibatchReportNr>stopAtMinibatch:
          break



if not np.any(session.run(checkNA)):
  session.run(scalePredictId, feed_dict={ inputDropout: currentIDropout, hiddenDropout: currentDropout })
  session.run(scalePredictHd, feed_dict={ inputDropout: currentIDropout, hiddenDropout: currentDropout })

  if computeTrainPredictions:
    predDenseTrain=[]
    if not (sparseOutputData is None):
      predSparseTrain=trainSparseOutput.copy().astype(np.float32)
      predSparseTrain.data[:]=-1
    idxSamplesEval=[arr[1] for arr in sklearn.model_selection.KFold(n_splits=int(math.ceil(len(trainSamples)/batchSize)), shuffle=False).split(np.arange(len(trainSamples)))]
    for j in range(len(idxSamplesEval)):
      
      myfeedDict={
        inputDropout: 0.0,
        hiddenDropout: 0.0,
        is_training: False
      }
      
      if nrDenseFeatures>0.5:
        batchDenseX=trainDenseInput[idxSamplesEval[j]]
        myfeedDict.update({
          xDenseData: batchDenseX
        })
      
      if nrSparseFeatures>0.5:
        batchSparseX=trainSparseInput[idxSamplesEval[j],:].copy()
        batchSparseX.sort_indices()
        nonzx=batchSparseX.nonzero()
        valnonzx=(batchSparseX)[nonzx[0],nonzx[1]]
        myfeedDict.update({
          xIndices: np.int64(np.vstack(nonzx).T), 
          xValues: valnonzx.A.flatten(), 
          xDim: [len(idxSamplesEval[j]), batchSparseX.shape[1]]
        })
      
      if useDenseOutputNetPred:
        if compPerformanceTrain:
          batchDenseY=trainDenseOutput[idxSamplesEval[j]]
        predDenseTrain.append(session.run(predNetwork, feed_dict=myfeedDict))
      
      if not useDenseOutputNetPred:
        if compPerformanceTrain:
          batchSparseY=trainSparseOutput[idxSamplesEval[j]].copy()
          batchSparseY.sort_indices()
          nonzy=batchSparseY.nonzero()
          valnonzy=(batchSparseY)[nonzy[0],nonzy[1]]
          myfeedDict.update({
            yIndices: np.int64(np.vstack(nonzy).T)
          })
          predSparseTrain[min(idxSamplesEval[j])+nonzy[0],nonzy[1]]=session.run(predNetworkSparse, feed_dict=myfeedDict)
    
    if useDenseOutputNetPred:
      predDenseTrain=np.vstack(predDenseTrain)
      if compPerformanceTrain:
        sumTrainAUC=np.array(utilsLib.calculateAUCs(trainDenseOutput, predDenseTrain))
        sumTrainAP=np.array(utilsLib.calculateAPs(trainDenseOutput, predDenseTrain))
    
    if not useDenseOutputNetPred:
      if compPerformanceTrain:
        predSparseTrainTransposed=predSparseTrain.T.tocsr()
        #predSparseTrain=None
        predSparseTrainTransposed.sort_indices()
        sumTrainAUC=np.array(utilsLib.calculateSparseAUCs(trainSparseOutputTransposed, predSparseTrainTransposed))
        sumTrainAP=np.array(utilsLib.calculateSparseAPs(trainSparseOutputTransposed, predSparseTrainTransposed))
        #predSparseTrainTransposed=None
    
    if compPerformanceTrain:
      #reportTrainAUC.append(sumTrainAUC)
      #reportTrainAP.append(sumTrainAP)
      print("\n", file=dbgOutput)
      # print("Train AUC: ", file=dbgOutput)
      # print(sumTrainAUC[0:500], file=dbgOutput)
      # print("\n", file=dbgOutput)
      # print("Train AP: ", file=dbgOutput)
      # print(sumTrainAP[0:500], file=dbgOutput)
      # print("\n", file=dbgOutput)
      print("Train Mean AUC: ", file=dbgOutput)
      print(np.nanmean(sumTrainAUC), file=dbgOutput)
      print("\n", file=dbgOutput)
      # print("Train Mean AP: ", file=dbgOutput)
      # print(np.nanmean(sumTrainAP), file=dbgOutput)
      # print("\n", file=dbgOutput)
      dbgOutput.flush()
  
  if computeTestPredictions:
    predDenseTest=[]
    if not (sparseOutputData is None):
      predSparseTest=testSparseOutput.copy().astype(np.float32)
      predSparseTest.data[:]=-1
    
    idxSamplesEval=[arr[1] for arr in sklearn.model_selection.KFold(n_splits=int(math.ceil(len(testSamples)/batchSize)), shuffle=False).split(np.arange(len(testSamples)))]
    for j in range(len(idxSamplesEval)):
      
      myfeedDict={
        inputDropout: 0.0,
        hiddenDropout: 0.0,
        is_training: False
      }
      
      if nrDenseFeatures>0.5:
        batchDenseX=testDenseInput[idxSamplesEval[j]]
        myfeedDict.update({
          xDenseData: batchDenseX
        })
      
      if nrSparseFeatures>0.5:
        batchSparseX=testSparseInput[idxSamplesEval[j],:].copy()
        batchSparseX.sort_indices()
        nonzx=batchSparseX.nonzero()
        valnonzx=(batchSparseX)[nonzx[0],nonzx[1]]
        myfeedDict.update({
          xIndices: np.int64(np.vstack(nonzx).T), 
          xValues: valnonzx.A.flatten(), 
          xDim: [len(idxSamplesEval[j]), batchSparseX.shape[1]]
        })
      
      if useDenseOutputNetPred:
        if compPerformanceTest:
          batchDenseY=testDenseOutput[idxSamplesEval[j]]
        predDenseTest.append(session.run(predNetwork, feed_dict=myfeedDict))
      
      if not useDenseOutputNetPred:
        if compPerformanceTest:
          batchSparseY=testSparseOutput[idxSamplesEval[j]].copy()
          batchSparseY.sort_indices()
          nonzy=batchSparseY.nonzero()
          valnonzy=(batchSparseY)[nonzy[0],nonzy[1]]
          myfeedDict.update({
            yIndices: np.int64(np.vstack(nonzy).T)
          })
          predSparseTest[min(idxSamplesEval[j])+nonzy[0],nonzy[1]]=session.run(predNetworkSparse, feed_dict=myfeedDict)
    
    if useDenseOutputNetPred:
      predDenseTest=np.vstack(predDenseTest)
      if compPerformanceTest:
        sumTestAUC=np.array(utilsLib.calculateAUCs(testDenseOutput, predDenseTest))
        sumTestAP=np.array(utilsLib.calculateAPs(testDenseOutput, predDenseTest))
    
    if not useDenseOutputNetPred:
      if compPerformanceTest:
        predSparseTestTransposed=predSparseTest.copy().T.tocsr()
        #predSparseTest=None
        predSparseTestTransposed.sort_indices()
        sumTestAUC=np.array(utilsLib.calculateSparseAUCs(testSparseOutputTransposed, predSparseTestTransposed))
        sumTestAP=np.array(utilsLib.calculateSparseAPs(testSparseOutputTransposed, predSparseTestTransposed))
        #predSparseTestTransposed=None
    
    
    
    if compPerformanceTest:
      #reportTestAUC.append(sumTestAUC)
      #reportTestAP.append(sumTestAP)
      print("\n", file=dbgOutput)
      # print("Test AUC: ", file=dbgOutput)
      # print(sumTestAUC[0:500], file=dbgOutput)
      # print("\n", file=dbgOutput)
      # print("Test AP: ", file=dbgOutput)
      # print(sumTestAP[0:500], file=dbgOutput)
      # print("\n", file=dbgOutput)
      print("Test Mean AUC: ", file=dbgOutput)
      print(np.nanmean(sumTestAUC), file=dbgOutput)
      print("\n", file=dbgOutput)
      # print("Test Mean AP: ", file=dbgOutput)
      # print(np.nanmean(sumTestAP), file=dbgOutput)
      # print("\n", file=dbgOutput)
      dbgOutput.flush()

  session.run(scaleTrainId, feed_dict={ inputDropout: currentIDropout, hiddenDropout: currentDropout })
  session.run(scaleTrainHd, feed_dict={ inputDropout: currentIDropout, hiddenDropout: currentDropout })



if saveComputations and saveScript!="":
  exec(open(saveScript).read(), globals())