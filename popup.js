document.getElementById('scrapeButton').addEventListener('click', function() {
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
      let currentUrl = tabs[0].url;
      
      // Check if the URL is from Flipkart
      if (!currentUrl.includes('flipkart.com')) {
        document.getElementById('result').innerText = "This is not a Flipkart page. Please navigate to a Flipkart page and try again.";
        return;
      }
  
      fetch('http://localhost:8000/scrape', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: currentUrl
        }),
      })
      .then(response => response.json())
      .then(data => {
        document.getElementById('result').innerText = JSON.stringify(data, null, 2);
      })
      .catch((error) => {
        console.error('Error:', error);
        document.getElementById('result').innerText = "An error occurred: " + error.message;
      });
    });
  });